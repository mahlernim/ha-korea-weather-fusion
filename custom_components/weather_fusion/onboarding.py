"""Location resolution and shared, capability-aware source validation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .catalog import get_location
from .configuration import WeatherFusionSettings
from .const import FORECAST_KEYS, WEATHERI_AIR_MAX_AGE
from .http import async_fetch_page
from .kma import (
    KmaConnectionError,
    KmaLocationError,
    ResolvedKmaLocation,
    async_resolve_location,
    parse_current_weather,
)
from .naver import parse_air as parse_naver_air
from .naver import parse_weather_snapshot
from .source import KOREA_TZ
from .weatheri import (
    WeatheriError,
    async_fetch_html,
    discover_air_stations,
    parse_air,
    parse_forecast,
)


class GuidedSetupError(Exception):
    def __init__(self, translation_key: str):
        super().__init__(translation_key)
        self.translation_key = translation_key


@dataclass(frozen=True, slots=True)
class GuidedSetup:
    values: dict[str, str]
    location_label: str
    resolved_kma: ResolvedKmaLocation
    stations: tuple[str, ...]
    weatheri_air_html: str

    @property
    def kma_location_label(self):
        if self.values["kma_code"] != self.resolved_kma.zone.code:
            return self.values["kma_code"]
        return self.resolved_kma.zone.name

    @property
    def kma_fallback(self):
        return (
            not self.resolved_kma.exact_city_match
            and self.values["kma_code"] == self.resolved_kma.zone.code
        )


@dataclass
class ValidationReport:
    """Available capabilities can support an explicitly limited setup."""

    available: dict[str, set[str]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    checked_at: datetime | None = None

    @property
    def usable(self):
        return any(self.available.values())

    @property
    def complete(self):
        return not any(source != "naver_air" for source in self.errors)

    @property
    def missing(self):
        required = {
            "kma": {"temperature", "humidity", "wind_speed"},
            "naver_weather": {"temperature", "humidity", "daily", *FORECAST_KEYS},
            "naver_air": {"pm10", "pm25"},
            "weatheri_forecast": {"daily"},
            "weatheri_air": {"pm10", "pm25"},
        }
        return {
            source: sorted(fields - self.available.get(source, set()))
            for source, fields in required.items()
            if source in self.errors
        }


async def async_prepare_guided_setup(hass, location_id, overrides=None):
    try:
        location = get_location(location_id)
    except ValueError as err:
        raise GuidedSetupError("invalid_location") from err
    session = async_get_clientsession(hass)
    try:
        resolved = await async_resolve_location(session, location)
    except KmaConnectionError as err:
        raise GuidedSetupError("cannot_connect_kma") from err
    except KmaLocationError as err:
        raise GuidedSetupError("cannot_resolve_kma") from err
    place = location.label.replace(" · ", " ")
    values = {
        "location_id": location.rid,
        "kma_code": resolved.zone.code,
        "naver_weather_query": f"{place} 날씨",
        "naver_air_query": f"{place} 미세먼지",
        "weatheri_forecast_rid": location.rid,
        "weatheri_forecast_group": location.forecast_group,
        "weatheri_location": location.name,
        "weatheri_air_region_code": location.air_region_code,
        "weatheri_air_station": "",
    }
    if overrides:
        values.update(overrides)
    try:
        html = await async_fetch_html(
            session, WeatherFusionSettings.from_mapping(values).weatheri_air_url
        )
        stations = await hass.async_add_executor_job(discover_air_stations, html)
    except WeatheriError as err:
        raise GuidedSetupError("cannot_connect_weatheri") from err
    return GuidedSetup(
        values,
        location.label,
        resolved,
        _rank_stations(location.label, tuple(stations)),
        html,
    )


def finalize_guided_values(guided, station):
    """Air-station selection must not silently change the weather location."""
    return {**guided.values, "weatheri_air_station": station}


async def async_validate_sources(hass, values, previous=None):
    """Validate all sources, or retry failures while keeping recent valid checks."""
    settings = WeatherFusionSettings.from_mapping(values)
    session = async_get_clientsession(hass)
    now = dt_util.utcnow().astimezone(KOREA_TZ)
    report = ValidationReport(checked_at=now)
    if (
        previous
        and previous.checked_at
        and now - previous.checked_at < timedelta(minutes=5)
    ):
        report.available = {
            key: set(value) for key, value in previous.available.items()
        }
        report.errors = dict(previous.errors)
        # Keep the age of reused successes; repeated retries must not renew them.
        report.checked_at = previous.checked_at
    urls = {
        "kma": settings.kma_url,
        "naver_weather": settings.naver_weather_url,
        "naver_air": settings.naver_air_url,
        "weatheri_forecast": settings.weatheri_forecast_url,
        "weatheri_air": settings.weatheri_air_url,
    }
    wanted = [
        key for key in urls if key not in report.available or key in report.errors
    ]

    async def check(source):
        available = set()
        try:
            fetch = (
                async_fetch_html if source.startswith("weatheri") else async_fetch_page
            )
            html = await fetch(session, urls[source])
            if source == "kma":
                data = await hass.async_add_executor_job(parse_current_weather, html)
                available.update(data)
                required = {"temperature", "humidity", "wind_speed"}
            elif source == "naver_weather":
                data = await hass.async_add_executor_job(
                    parse_weather_snapshot, html, now
                )
                available.update(
                    data.numeric.keys()
                    - {"today_high", "today_low", "tomorrow_high", "tomorrow_low"}
                )
                if {now.date(), now.date() + timedelta(days=1)} <= {
                    item.day for item in data.daily
                }:
                    available.add("daily")
                targets = {item.time for item in data.hourly if item.text}
                for key in FORECAST_KEYS:
                    target = now.replace(minute=0, second=0, microsecond=0) + timedelta(
                        hours=int(key[9:-1])
                    )
                    if target in targets:
                        available.add(key)
                required = {"temperature", "humidity", "daily", *FORECAST_KEYS}
            elif source == "naver_air":
                data, _ = await hass.async_add_executor_job(parse_naver_air, html)
                available.update(data)
                required = {"pm10", "pm25"}
            elif source == "weatheri_forecast":
                await hass.async_add_executor_job(
                    partial(
                        parse_forecast,
                        html,
                        location=settings.weatheri_location,
                        current_date=now.date(),
                        fetched_at=now,
                    )
                )
                available.add("daily")
                required = {"daily"}
            else:
                data = await hass.async_add_executor_job(
                    partial(
                        parse_air,
                        html,
                        station=settings.weatheri_air_station,
                        fetched_at=now,
                        local_tz=KOREA_TZ,
                    )
                )
                if (
                    not timedelta(0)
                    <= now - data.source_updated_at
                    <= WEATHERI_AIR_MAX_AGE
                ):
                    return source, set(), "stale_data"
                available.update(
                    key for key, value in data.measurements.items() if value is not None
                )
                required = {"pm10", "pm25"}
            return source, available, None if required <= available else "missing_data"
        except (WeatheriError, ValueError, OSError, TimeoutError, aiohttp.ClientError):
            return source, available, "cannot_validate"

    for source, available, error in await asyncio.gather(
        *(check(source) for source in wanted)
    ):
        report.available[source] = available
        if error:
            report.errors[source] = error
        else:
            report.errors.pop(source, None)
    return report


def _rank_stations(location_label, stations):
    parts = location_label.split(" · ", maxsplit=1)
    if len(parts) == 1:
        return stations
    wanted = _normalized_place_name(parts[1])
    return tuple(
        sorted(stations, key=lambda station: _normalized_place_name(station) != wanted)
    )


def _normalized_place_name(value):
    normalized = value.replace(" ", "")
    for suffix in ("특별자치시", "광역시", "특별시", "시", "군", "구"):
        if len(normalized) > 2 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized
