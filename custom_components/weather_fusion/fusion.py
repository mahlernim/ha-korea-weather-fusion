"""State-driven fusion logic."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from statistics import fmean
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import (
    async_call_later,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .configuration import WeatherFusionSettings
from .const import (
    CURRENT_MAX_AGE,
    DOMAIN,
    FORECAST_KEYS,
    FORECAST_MAX_AGE,
    KMA_METRIC_KEYS,
    KMA_SCAN_INTERVAL,
    METRIC_KEYS,
    NAVER_NUMERIC_KEYS,
    NAVER_SCAN_INTERVAL,
    NAVER_TEXT_KEYS,
    REEVALUATE_INTERVAL,
    SOURCE_GROUPS,
    WEATHERI_AIR_MAX_AGE,
    WEATHERI_NUMERIC_KEYS,
    WEATHERI_RETRY_DELAYS,
    WEATHERI_SCAN_INTERVAL,
)
from .kma import parse_current_weather
from .naver import parse_air, parse_weather
from .source import SourceSnapshot
from .weatheri import (
    AIR_KEYS,
    WeatheriAir,
    WeatheriError,
    WeatheriForecast,
    async_fetch_html,
)
from .weatheri import (
    parse_air as parse_weatheri_air,
)
from .weatheri import (
    parse_forecast as parse_weatheri_forecast,
)


@dataclass(frozen=True, slots=True)
class FusionResult:
    """One numeric fused metric and its audit details."""

    value: float | None
    selected_sources: tuple[str, ...]
    eligible_sources: dict[str, float]
    rejected_sources: dict[str, str]

    @property
    def attributes(self) -> dict[str, Any]:
        return {
            "selected_sources": list(self.selected_sources),
            "eligible_sources": self.eligible_sources,
            "rejected_sources": self.rejected_sources,
        }


@dataclass(frozen=True, slots=True)
class TextResult:
    """One text forecast and its audit details."""

    value: str | None
    selected_source: str | None
    rejected_sources: dict[str, str]

    @property
    def attributes(self) -> dict[str, Any]:
        return {
            "selected_sources": [self.selected_source] if self.selected_source else [],
            "rejected_sources": self.rejected_sources,
        }


@dataclass(frozen=True, slots=True)
class Candidate:
    """A candidate source for a fused metric."""

    source: str
    source_group: str
    key: str
    max_age: timedelta


@dataclass(frozen=True, slots=True)
class KmaSample:
    """One direct weather.go.kr sample."""

    value: float
    last_reported: datetime


class WeatherFusionEngine:
    """Combine normalized source snapshots without knowing entity IDs."""

    def __init__(
        self, snapshots: dict[str, SourceSnapshot], now: datetime | None = None
    ) -> None:
        self.snapshots = snapshots
        self.now = now or dt_util.utcnow()

    def _source_freshness_reason(self, group: str, max_age: timedelta) -> str | None:
        snapshot = self.snapshots.get(group)
        if snapshot is None:
            return f"source_snapshot_missing:{group}"
        if snapshot.last_reported is None:
            if snapshot.unavailable_reason:
                return snapshot.unavailable_reason
            return f"source_activity_missing:{group}"
        age = self.now - snapshot.last_reported
        if age > max_age:
            return f"source_stale:{group}:{round(age.total_seconds() / 60)}m"
        return snapshot.unavailable_reason

    def _candidate_value(self, candidate: Candidate) -> tuple[float | None, str | None]:
        if reason := self._source_freshness_reason(
            candidate.source_group, candidate.max_age
        ):
            return None, reason
        snapshot = self.snapshots[candidate.source_group]
        if candidate.key in snapshot.value_errors:
            return None, snapshot.value_errors[candidate.key]
        value = snapshot.numeric.get(candidate.key)
        if value is None:
            return None, "value_missing"
        if not math.isfinite(value):
            return None, "non_finite"
        return value, None

    def _combine(self, candidates: tuple[Candidate, ...], mode: str) -> FusionResult:
        eligible: dict[str, float] = {}
        rejected: dict[str, str] = {}
        for candidate in candidates:
            value, reason = self._candidate_value(candidate)
            if value is None:
                rejected[candidate.source] = reason or "invalid"
            else:
                eligible[candidate.source] = value
        if not eligible:
            return FusionResult(None, (), {}, rejected)
        if mode == "mean":
            selected = tuple(eligible)
            value = fmean(eligible.values())
        else:
            selected = (next(iter(eligible)),)
            value = eligible[selected[0]]
        return FusionResult(round(value, 1), selected, eligible, rejected)

    def metric(self, key: str) -> FusionResult:
        """Return the current value and source audit for a numeric metric."""
        if key in ("temperature", "humidity", "wind_speed"):
            return self._combine(
                (
                    Candidate("naver", "naver_weather", key, CURRENT_MAX_AGE),
                    Candidate("weather_go_kr", "weather_go_kr", key, CURRENT_MAX_AGE),
                ),
                "mean",
            )
        if key in ("pm10", "pm25"):
            return self._combine(
                (
                    Candidate("weatheri", "weatheri_air", key, WEATHERI_AIR_MAX_AGE),
                    Candidate("weather_go_kr", "weather_go_kr", key, CURRENT_MAX_AGE),
                    Candidate("naver", "naver_air", key, CURRENT_MAX_AGE),
                ),
                "priority",
            )
        if key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low"):
            return self._combine(
                (
                    Candidate("naver", "naver_weather", key, FORECAST_MAX_AGE),
                    Candidate("weatheri", "weatheri_forecast", key, FORECAST_MAX_AGE),
                ),
                "priority",
            )
        raise ValueError(f"Unknown metric: {key}")

    def source_metric(
        self, source: str, group: str, key: str, max_age: timedelta
    ) -> FusionResult:
        """Return one raw numeric metric from a normalized snapshot."""
        value, reason = self._candidate_value(Candidate(source, group, key, max_age))
        if value is None:
            return FusionResult(None, (), {}, {source: reason or "invalid"})
        return FusionResult(value, (source,), {source: value}, {})

    def source_text(
        self, source: str, group: str, key: str, max_age: timedelta
    ) -> TextResult:
        """Return one text metric from a normalized snapshot."""
        if reason := self._source_freshness_reason(group, max_age):
            return TextResult(None, None, {source: reason})
        snapshot = self.snapshots[group]
        if key in snapshot.value_errors:
            return TextResult(None, None, {source: snapshot.value_errors[key]})
        value = snapshot.text.get(key)
        if value is None:
            return TextResult(None, None, {source: "value_missing"})
        return TextResult(value, source, {})

    def forecast(self, key: str) -> TextResult:
        """Pass through one fresh Naver text forecast with source audit."""
        if key not in FORECAST_KEYS:
            raise ValueError(f"Unknown forecast: {key}")
        if reason := self._source_freshness_reason("naver_weather", FORECAST_MAX_AGE):
            return TextResult(None, None, {"naver": reason})
        snapshot = self.snapshots["naver_weather"]
        if key in snapshot.value_errors:
            return TextResult(None, None, {"naver": snapshot.value_errors[key]})
        value = snapshot.text.get(key)
        if value is None:
            return TextResult(None, None, {"naver": "value_missing"})
        return TextResult(value, "naver", {})


class WeatherFusionManager:
    """Watch upstream entities and notify all fusion entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str = DOMAIN,
        weatheri_store: Store[dict[str, Any]] | None = None,
        settings: WeatherFusionSettings | None = None,
    ) -> None:
        self.hass = hass
        if settings is None:
            raise ValueError("Korea Weather Fusion settings are required")
        self.settings = settings
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_timer: Callable[[], None] | None = None
        self._unsub_kma_timer: Callable[[], None] | None = None
        self._unsub_naver_timer: Callable[[], None] | None = None
        self._unsub_weatheri_timer: Callable[[], None] | None = None
        self._unsub_weatheri_retry: Callable[[], None] | None = None
        self._unsub_weatheri_midnight: Callable[[], None] | None = None
        self._kma_samples: dict[str, KmaSample] = {}
        self._kma_last_attempt: datetime | None = None
        self._kma_last_success: datetime | None = None
        self._kma_last_error: str | None = None
        self._naver_snapshots = {
            group: SourceSnapshot(group=group, last_reported=None)
            for group in ("naver_weather", "naver_air")
        }
        self._naver_last_attempt: dict[str, datetime | None] = {
            group: None for group in self._naver_snapshots
        }
        self._naver_last_error: dict[str, str | None] = {
            group: None for group in self._naver_snapshots
        }
        self._weatheri_forecast: WeatheriForecast | None = None
        self._weatheri_air: WeatheriAir | None = None
        self._weatheri_last_attempt: dict[str, datetime | None] = {
            "weatheri_forecast": None,
            "weatheri_air": None,
        }
        self._weatheri_last_success: dict[str, datetime | None] = {
            "weatheri_forecast": None,
            "weatheri_air": None,
        }
        self._weatheri_last_error: dict[str, str | None] = {
            "weatheri_forecast": None,
            "weatheri_air": None,
        }
        self._weatheri_using_cache = {
            "weatheri_forecast": False,
            "weatheri_air": False,
        }
        self._weatheri_retry_count = 0
        self._weatheri_store = weatheri_store or Store(
            hass, 1, f"{DOMAIN}.{entry_id}.weatheri"
        )

    async def async_initialize(self) -> None:
        """Restore persistent Weatheri snapshots and attempt a fresh update."""
        await self._async_load_weatheri_cache()
        await self.async_update_weatheri()

    @callback
    def async_start(self) -> None:
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_timer, REEVALUATE_INTERVAL
        )
        self._unsub_kma_timer = async_track_time_interval(
            self.hass, self._async_kma_timer, KMA_SCAN_INTERVAL
        )
        self._unsub_naver_timer = async_track_time_interval(
            self.hass, self._async_naver_timer, NAVER_SCAN_INTERVAL
        )
        self._unsub_weatheri_timer = async_track_time_interval(
            self.hass, self._async_weatheri_timer, WEATHERI_SCAN_INTERVAL
        )
        self._schedule_weatheri_midnight()
        self.hass.async_create_task(self.async_update_kma())
        self.hass.async_create_task(self.async_update_naver())

    @callback
    def async_stop(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_kma_timer:
            self._unsub_kma_timer()
            self._unsub_kma_timer = None
        if self._unsub_naver_timer:
            self._unsub_naver_timer()
            self._unsub_naver_timer = None
        if self._unsub_weatheri_timer:
            self._unsub_weatheri_timer()
            self._unsub_weatheri_timer = None
        if self._unsub_weatheri_retry:
            self._unsub_weatheri_retry()
            self._unsub_weatheri_retry = None
        if self._unsub_weatheri_midnight:
            self._unsub_weatheri_midnight()
            self._unsub_weatheri_midnight = None
        self._listeners.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _async_timer(self, now: datetime) -> None:
        self._notify()

    async def _async_kma_timer(self, now: datetime) -> None:
        await self.async_update_kma()

    async def _async_naver_timer(self, now: datetime) -> None:
        await self.async_update_naver()

    async def _async_weatheri_timer(self, now: datetime) -> None:
        await self.async_update_weatheri()

    async def async_update_naver(self) -> None:
        """Refresh Naver groups independently and retain last good snapshots."""
        session = async_get_clientsession(self.hass)
        for group, url in (
            ("naver_weather", self.settings.naver_weather_url),
            ("naver_air", self.settings.naver_air_url),
        ):
            self._naver_last_attempt[group] = dt_util.utcnow()
            try:
                async with session.get(
                    url,
                    timeout=20,
                    headers={"User-Agent": "Home Assistant Korea Weather Fusion"},
                ) as response:
                    response.raise_for_status()
                    html = await response.text()
                if group == "naver_weather":
                    numeric, text, value_errors = parse_weather(html)
                else:
                    numeric, value_errors = parse_air(html)
                    text = {}
            except (TimeoutError, ClientError, ValueError, UnicodeDecodeError) as err:
                self._naver_last_error[group] = f"{type(err).__name__}: {err}"
                continue

            self._naver_snapshots[group] = SourceSnapshot(
                group=group,
                last_reported=dt_util.utcnow(),
                numeric=numeric,
                text=text,
                value_errors=value_errors,
            )
            self._naver_last_error[group] = None
        self._notify()

    async def _async_load_weatheri_cache(self) -> None:
        try:
            stored = await self._weatheri_store.async_load()
        except (OSError, ValueError, TypeError):
            stored = None
        if not stored:
            return
        now = dt_util.now()
        if raw_forecast := stored.get("forecast"):
            try:
                forecast = WeatheriForecast.from_dict(raw_forecast)
                if (
                    forecast.location == self.settings.weatheri_location
                    and forecast.source_date == now.date()
                ):
                    self._weatheri_forecast = forecast
                    self._weatheri_last_success["weatheri_forecast"] = (
                        forecast.fetched_at
                    )
                    self._weatheri_using_cache["weatheri_forecast"] = True
            except (KeyError, TypeError, ValueError):
                self._weatheri_forecast = None
        if raw_air := stored.get("air"):
            try:
                air = WeatheriAir.from_dict(raw_air)
                age = now - air.source_updated_at
                if (
                    air.station == self.settings.weatheri_air_station
                    and timedelta(0) <= age <= WEATHERI_AIR_MAX_AGE
                ):
                    self._weatheri_air = air
                    self._weatheri_last_success["weatheri_air"] = air.fetched_at
                    self._weatheri_using_cache["weatheri_air"] = True
            except (KeyError, TypeError, ValueError):
                self._weatheri_air = None

    async def async_update_weatheri(self) -> None:
        """Refresh Weatheri forecast and air independently with cached fallback."""
        session = async_get_clientsession(self.hass)
        now = dt_util.now()
        group = "weatheri_forecast"
        self._weatheri_last_attempt[group] = now
        try:
            html = await async_fetch_html(session, self.settings.weatheri_forecast_url)
            forecast = await self.hass.async_add_executor_job(
                partial(
                    parse_weatheri_forecast,
                    html,
                    location=self.settings.weatheri_location,
                    current_date=now.date(),
                    fetched_at=now,
                )
            )
        except WeatheriError as err:
            self._weatheri_last_error[group] = str(err)
            if (
                self._weatheri_forecast is None
                or self._weatheri_forecast.source_date != now.date()
            ):
                self._weatheri_forecast = None
                self._schedule_weatheri_retry()
            else:
                self._weatheri_using_cache[group] = True
        else:
            self._weatheri_forecast = forecast
            self._weatheri_last_success[group] = now
            self._weatheri_last_error[group] = None
            self._weatheri_using_cache[group] = False
            self._weatheri_retry_count = 0
            if self._unsub_weatheri_retry:
                self._unsub_weatheri_retry()
                self._unsub_weatheri_retry = None

        group = "weatheri_air"
        air_now = dt_util.now()
        self._weatheri_last_attempt[group] = air_now
        try:
            html = await async_fetch_html(session, self.settings.weatheri_air_url)
            air = await self.hass.async_add_executor_job(
                partial(
                    parse_weatheri_air,
                    html,
                    station=self.settings.weatheri_air_station,
                    fetched_at=air_now,
                    local_tz=air_now.tzinfo,
                )
            )
        except WeatheriError as err:
            self._weatheri_last_error[group] = str(err)
            if (
                self._weatheri_air is None
                or not timedelta(0)
                <= air_now - self._weatheri_air.source_updated_at
                <= WEATHERI_AIR_MAX_AGE
            ):
                self._weatheri_air = None
            else:
                self._weatheri_using_cache[group] = True
        else:
            self._weatheri_air = air
            self._weatheri_last_success[group] = air_now
            self._weatheri_last_error[group] = None
            self._weatheri_using_cache[group] = False

        await self._weatheri_store.async_save(
            {
                "forecast": self._weatheri_forecast.as_dict()
                if self._weatheri_forecast
                else None,
                "air": self._weatheri_air.as_dict() if self._weatheri_air else None,
            }
        )
        self._notify()

    def _schedule_weatheri_retry(self) -> None:
        if self._unsub_weatheri_retry:
            return
        delay = WEATHERI_RETRY_DELAYS[
            min(self._weatheri_retry_count, len(WEATHERI_RETRY_DELAYS) - 1)
        ]
        self._weatheri_retry_count += 1

        @callback
        def retry(_now: datetime) -> None:
            self._unsub_weatheri_retry = None
            self.hass.async_create_task(self.async_update_weatheri())

        self._unsub_weatheri_retry = async_call_later(
            self.hass, delay.total_seconds(), retry
        )

    def _schedule_weatheri_midnight(self) -> None:
        if self._unsub_weatheri_midnight:
            self._unsub_weatheri_midnight()
        now = dt_util.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )

        @callback
        def rollover(_now: datetime) -> None:
            self._unsub_weatheri_midnight = None
            self._notify()
            self.hass.async_create_task(self.async_update_weatheri())
            self._schedule_weatheri_midnight()

        self._unsub_weatheri_midnight = async_call_later(
            self.hass, (midnight - now).total_seconds() + 0.1, rollover
        )

    async def async_update_kma(self) -> None:
        """Fetch direct weather.go.kr values without surfacing transient failures."""
        self._kma_last_attempt = dt_util.utcnow()
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self.settings.kma_url, timeout=20) as response:
                response.raise_for_status()
                html = await response.text()
            values = self._parse_kma_html(html)
        except (TimeoutError, ClientError, ValueError, UnicodeDecodeError) as err:
            self._kma_last_error = f"{type(err).__name__}: {err}"
            self._notify()
            return

        reported = dt_util.utcnow()
        self._kma_samples = {
            key: KmaSample(value=value, last_reported=reported)
            for key, value in values.items()
        }
        self._kma_last_success = reported
        self._kma_last_error = None
        self._notify()

    def _parse_kma_html(self, html: str) -> dict[str, float]:
        """Extract current weather.go.kr values from the rendered fragment."""
        return parse_current_weather(html)

    def _naver_snapshot(self, group: str) -> SourceSnapshot:
        snapshot = self._naver_snapshots[group]
        error = self._naver_last_error[group]
        url = (
            self.settings.naver_weather_url
            if group == "naver_weather"
            else self.settings.naver_air_url
        )
        return SourceSnapshot(
            group=group,
            last_reported=snapshot.last_reported,
            numeric=snapshot.numeric,
            text=snapshot.text,
            value_errors=snapshot.value_errors,
            unavailable_reason=(
                f"source_unavailable:{group}:{error}"
                if snapshot.last_reported is None and error
                else None
            ),
            attributes={
                "last_attempt": self._naver_last_attempt[group].isoformat()
                if self._naver_last_attempt[group]
                else None,
                "last_success": snapshot.last_reported.isoformat()
                if snapshot.last_reported
                else None,
                "last_error": error,
                "source_url": url,
            },
        )

    def _weatheri_snapshot(self, group: str) -> SourceSnapshot:
        now = dt_util.now()
        attributes: dict[str, Any] = {
            "last_attempt": self._weatheri_last_attempt[group].isoformat()
            if self._weatheri_last_attempt[group]
            else None,
            "last_success": self._weatheri_last_success[group].isoformat()
            if self._weatheri_last_success[group]
            else None,
            "last_error": self._weatheri_last_error[group],
            "using_cached_data": self._weatheri_using_cache[group],
        }
        if group == "weatheri_forecast":
            forecast = self._weatheri_forecast
            attributes.update(
                {
                    "source_url": self.settings.weatheri_forecast_url,
                    "location": self.settings.weatheri_location,
                    "source_date": forecast.source_date.isoformat()
                    if forecast
                    else None,
                    "rollover_retry_count": self._weatheri_retry_count,
                }
            )
            current = forecast is not None and forecast.source_date == now.date()
            return SourceSnapshot(
                group=group,
                last_reported=forecast.fetched_at if current else None,
                numeric=(
                    {
                        "today_high": forecast.today_high,
                        "today_low": forecast.today_low,
                        "tomorrow_high": forecast.tomorrow_high,
                        "tomorrow_low": forecast.tomorrow_low,
                    }
                    if current
                    else {}
                ),
                unavailable_reason=(
                    None
                    if current
                    else self._weatheri_last_error[group]
                    or "weatheri_forecast_not_current"
                ),
                attributes=attributes,
            )

        air = self._weatheri_air
        age = now - air.source_updated_at if air else None
        fresh = (
            air is not None
            and age is not None
            and timedelta(0) <= age <= WEATHERI_AIR_MAX_AGE
        )
        attributes.update(
            {
                "source_url": self.settings.weatheri_air_url,
                "station": self.settings.weatheri_air_station,
                "source_updated_at": air.source_updated_at.isoformat() if air else None,
                "data_age_minutes": round(age.total_seconds() / 60, 1)
                if age is not None
                else None,
            }
        )
        numeric = (
            {key: value for key, value in air.measurements.items() if value is not None}
            if fresh and air
            else {}
        )
        errors = (
            {
                key: f"weatheri_metric_missing:{key}"
                for key in AIR_KEYS
                if air and air.measurements.get(key) is None
            }
            if fresh
            else {}
        )
        return SourceSnapshot(
            group=group,
            last_reported=air.source_updated_at if fresh and air else None,
            numeric=numeric,
            value_errors=errors,
            unavailable_reason=(
                None
                if fresh
                else self._weatheri_last_error[group] or "weatheri_air_not_current"
            ),
            attributes=attributes,
        )

    def source_snapshots(self) -> dict[str, SourceSnapshot]:
        """Normalize current external states and direct KMA data."""
        kma_errors = {
            key: f"kma_metric_missing:{key}"
            for key in KMA_METRIC_KEYS
            if key not in self._kma_samples
        }
        kma_unavailable = None
        if self._kma_last_success is None and self._kma_last_error:
            kma_unavailable = f"source_unavailable:weather_go_kr:{self._kma_last_error}"
        snapshots = {
            "naver_weather": self._naver_snapshot("naver_weather"),
            "naver_air": self._naver_snapshot("naver_air"),
            "weatheri_forecast": self._weatheri_snapshot("weatheri_forecast"),
            "weatheri_air": self._weatheri_snapshot("weatheri_air"),
            "weather_go_kr": SourceSnapshot(
                group="weather_go_kr",
                last_reported=self._kma_last_success,
                numeric={
                    key: sample.value for key, sample in self._kma_samples.items()
                },
                value_errors=kma_errors,
                unavailable_reason=kma_unavailable,
                attributes={
                    "last_attempt": self._kma_last_attempt.isoformat()
                    if self._kma_last_attempt
                    else None,
                    "last_success": self._kma_last_success.isoformat()
                    if self._kma_last_success
                    else None,
                    "last_error": self._kma_last_error,
                    "source_url": self.settings.kma_url,
                },
            ),
        }
        return snapshots

    def _engine(self) -> WeatherFusionEngine:
        return WeatherFusionEngine(self.source_snapshots())

    def source_activity(self, group: str) -> datetime | None:
        """Return the newest report represented by one normalized snapshot."""
        snapshot = self.source_snapshots().get(group)
        return snapshot.last_reported if snapshot else None

    def source_activity_attributes(self) -> dict[str, dict[str, Any]]:
        """Return timestamps and ages for all upstream resource groups."""
        now = dt_util.utcnow()
        snapshots = self.source_snapshots()
        result: dict[str, dict[str, Any]] = {}
        for group in SOURCE_GROUPS:
            snapshot = snapshots[group]
            reported = snapshot.last_reported
            attributes: dict[str, Any] = {
                "last_reported": reported.isoformat() if reported else None,
                "age_minutes": (
                    round((now - reported).total_seconds() / 60, 1)
                    if reported
                    else None
                ),
            }
            attributes.update(snapshot.attributes)
            result[group] = attributes
        return result

    def kma_metric(self, key: str) -> FusionResult:
        """Return one raw direct weather.go.kr metric with audit attributes."""
        if key not in KMA_METRIC_KEYS:
            return FusionResult(
                None, (), {}, {"weather_go_kr": f"unknown_kma_metric:{key}"}
            )
        return self._engine().source_metric(
            "weather_go_kr", "weather_go_kr", key, CURRENT_MAX_AGE
        )

    def kma_metric_attributes(self, key: str) -> dict[str, Any]:
        attributes = self.kma_metric(key).attributes
        attributes.update(self.source_snapshots()["weather_go_kr"].attributes)
        return attributes

    def naver_numeric_metric(self, key: str) -> FusionResult:
        """Return one raw direct Naver numeric metric."""
        if key not in NAVER_NUMERIC_KEYS:
            return FusionResult(None, (), {}, {"naver": f"unknown_naver_metric:{key}"})
        group = "naver_air" if key in ("pm10", "pm25") else "naver_weather"
        max_age = (
            FORECAST_MAX_AGE
            if key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low")
            else CURRENT_MAX_AGE
        )
        return self._engine().source_metric("naver", group, key, max_age)

    def naver_text_metric(self, key: str) -> TextResult:
        """Return one raw direct Naver text metric."""
        if key not in NAVER_TEXT_KEYS:
            return TextResult(None, None, {"naver": f"unknown_naver_metric:{key}"})
        max_age = FORECAST_MAX_AGE if key in FORECAST_KEYS else CURRENT_MAX_AGE
        return self._engine().source_text("naver", "naver_weather", key, max_age)

    def naver_metric_attributes(self, key: str) -> dict[str, Any]:
        """Return direct Naver audit and fetch attributes."""
        if key in NAVER_NUMERIC_KEYS:
            result = self.naver_numeric_metric(key)
            group = "naver_air" if key in ("pm10", "pm25") else "naver_weather"
        else:
            result = self.naver_text_metric(key)
            group = "naver_weather"
        attributes = result.attributes
        attributes.update(self.source_snapshots()[group].attributes)
        return attributes

    def weatheri_numeric_metric(self, key: str) -> FusionResult:
        """Return one raw direct Weatheri numeric metric."""
        if key not in WEATHERI_NUMERIC_KEYS:
            return FusionResult(
                None, (), {}, {"weatheri": f"unknown_weatheri_metric:{key}"}
            )
        group = (
            "weatheri_forecast"
            if key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low")
            else "weatheri_air"
        )
        max_age = (
            FORECAST_MAX_AGE if group == "weatheri_forecast" else WEATHERI_AIR_MAX_AGE
        )
        return self._engine().source_metric("weatheri", group, key, max_age)

    def weatheri_metric_attributes(self, key: str) -> dict[str, Any]:
        """Return direct Weatheri audit and fetch attributes."""
        group = (
            "weatheri_forecast"
            if key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low")
            else "weatheri_air"
        )
        attributes = self.weatheri_numeric_metric(key).attributes
        attributes.update(self.source_snapshots()[group].attributes)
        return attributes

    def weatheri_source_health(self, group: str) -> tuple[bool, dict[str, Any]]:
        """Return source-specific Weatheri health and diagnostics."""
        snapshot = self.source_snapshots()[group]
        if group == "weatheri_forecast":
            healthy = snapshot.last_reported is not None
        elif group == "weatheri_air":
            healthy = all(key in snapshot.numeric for key in ("pm10", "pm25"))
        else:
            raise ValueError(f"Unknown Weatheri source group: {group}")
        return healthy, {
            **snapshot.attributes,
            "missing_measurements": [
                key for key in AIR_KEYS if key not in snapshot.numeric
            ]
            if group == "weatheri_air"
            else [],
        }

    def metric(self, key: str) -> FusionResult:
        """Return one snapshot-driven fused numeric metric."""
        return self._engine().metric(key)

    def forecast(self, key: str) -> TextResult:
        """Return one snapshot-driven text forecast."""
        return self._engine().forecast(key)

    def health(self) -> tuple[bool, dict[str, Any]]:
        """Return all-numeric-metrics freshness and source audit."""
        results = {key: self.metric(key) for key in METRIC_KEYS}
        missing = [key for key, result in results.items() if result.value is None]
        return not missing, {
            "criteria": "all_representative_metrics_available",
            "available_metrics": [key for key in METRIC_KEYS if key not in missing],
            "missing_metrics": missing,
            "selected_sources": {
                key: list(result.selected_sources) for key, result in results.items()
            },
            "source_activity": self.source_activity_attributes(),
        }

    def forecast_health(self) -> tuple[bool, dict[str, Any]]:
        """Return text-forecast freshness separately from numeric health."""
        results = {key: self.forecast(key) for key in FORECAST_KEYS}
        missing = [key for key, result in results.items() if result.value is None]
        return not missing, {
            "criteria": "all_text_forecasts_available",
            "available_forecasts": [key for key in FORECAST_KEYS if key not in missing],
            "missing_forecasts": missing,
            "selected_sources": {
                key: result.selected_source for key, result in results.items()
            },
            "source_activity": {
                "naver_weather": self.source_activity_attributes()["naver_weather"]
            },
        }
