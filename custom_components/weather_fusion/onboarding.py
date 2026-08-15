"""Guided location resolution and setup validation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import partial

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .catalog import get_location
from .configuration import (
    CONF_KMA_CODE,
    CONF_LOCATION_ID,
    CONF_NAVER_AIR_QUERY,
    CONF_NAVER_WEATHER_QUERY,
    CONF_WEATHERI_AIR_REGION_CODE,
    CONF_WEATHERI_AIR_STATION,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_LOCATION,
    WeatherFusionSettings,
)
from .kma import (
    KmaConnectionError,
    KmaLocationError,
    ResolvedKmaLocation,
    async_refine_with_station,
    async_resolve_location,
    parse_current_weather,
)
from .naver import parse_weather as parse_naver_weather
from .weatheri import (
    WeatheriError,
    async_fetch_html,
    discover_air_stations,
)
from .weatheri import (
    parse_air as parse_weatheri_air,
)
from .weatheri import (
    parse_forecast as parse_weatheri_forecast,
)

_MAX_RESPONSE_BYTES = 1024 * 1024
_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
    "User-Agent": "Home Assistant Korea Weather Fusion",
}


class GuidedSetupError(Exception):
    """A translated config-flow error key."""

    def __init__(self, translation_key: str) -> None:
        super().__init__(translation_key)
        self.translation_key = translation_key


@dataclass(frozen=True, slots=True)
class GuidedSetup:
    """Resolved settings and cached Weatheri setup data."""

    values: dict[str, str]
    location_label: str
    resolved_kma: ResolvedKmaLocation
    stations: tuple[str, ...]
    weatheri_air_html: str

    @property
    def kma_location_label(self) -> str:
        """Return the KMA location shown in the station step."""
        return self.resolved_kma.zone.name


async def async_prepare_guided_setup(
    hass: HomeAssistant, location_id: str
) -> GuidedSetup:
    """Resolve source selectors and load valid Weatheri station choices."""
    try:
        location = get_location(location_id)
    except ValueError as err:
        raise GuidedSetupError("invalid_location") from err

    session = async_get_clientsession(hass)
    try:
        resolved_kma = await async_resolve_location(session, location)
    except KmaConnectionError as err:
        raise GuidedSetupError("cannot_connect_kma") from err
    except KmaLocationError as err:
        raise GuidedSetupError("cannot_resolve_kma") from err

    query_location = location.label.replace(" · ", " ")
    values = {
        CONF_LOCATION_ID: location.rid,
        CONF_KMA_CODE: resolved_kma.zone.code,
        CONF_NAVER_WEATHER_QUERY: f"{query_location} 날씨",
        CONF_NAVER_AIR_QUERY: f"{query_location} 미세먼지",
        CONF_WEATHERI_FORECAST_RID: location.rid,
        CONF_WEATHERI_FORECAST_GROUP: location.forecast_group,
        CONF_WEATHERI_LOCATION: location.name,
        CONF_WEATHERI_AIR_REGION_CODE: location.air_region_code,
        CONF_WEATHERI_AIR_STATION: "",
    }
    settings = WeatherFusionSettings.from_mapping(values)
    try:
        forecast_html, air_html = await asyncio.gather(
            async_fetch_html(session, settings.weatheri_forecast_url),
            async_fetch_html(session, settings.weatheri_air_url),
        )
    except WeatheriError as err:
        raise GuidedSetupError("cannot_connect_weatheri") from err

    now = dt_util.now()
    try:
        await hass.async_add_executor_job(
            partial(
                parse_weatheri_forecast,
                forecast_html,
                location=location.name,
                current_date=now.date(),
                fetched_at=now,
            )
        )
        stations = await hass.async_add_executor_job(discover_air_stations, air_html)
    except WeatheriError as err:
        raise GuidedSetupError("invalid_weatheri_data") from err

    return GuidedSetup(
        values=values,
        location_label=location.label,
        resolved_kma=resolved_kma,
        stations=_rank_stations(location.label, tuple(stations)),
        weatheri_air_html=air_html,
    )


async def async_finalize_guided_values(
    hass: HomeAssistant,
    guided: GuidedSetup,
    station: str,
) -> dict[str, str]:
    """Specialize KMA and Naver selectors with the chosen air station."""
    session = async_get_clientsession(hass)
    try:
        resolved_kma = await async_refine_with_station(
            session, guided.resolved_kma, station
        )
    except KmaConnectionError as err:
        raise GuidedSetupError("cannot_connect_kma") from err
    except KmaLocationError as err:
        raise GuidedSetupError("cannot_resolve_kma") from err

    query_location = _detailed_query_location(guided.location_label, station)
    return {
        **guided.values,
        CONF_KMA_CODE: resolved_kma.zone.code,
        CONF_NAVER_WEATHER_QUERY: f"{query_location} 날씨",
        CONF_NAVER_AIR_QUERY: f"{query_location} 미세먼지",
        CONF_WEATHERI_AIR_STATION: station,
    }


async def async_validate_guided_setup(
    hass: HomeAssistant,
    values: dict[str, str],
    *,
    weatheri_air_html: str,
) -> dict[str, str]:
    """Validate required feeds and the chosen Weatheri station."""
    settings = WeatherFusionSettings.from_mapping(values)
    session = async_get_clientsession(hass)
    results = await asyncio.gather(
        _async_fetch_page(session, settings.kma_url),
        _async_fetch_page(session, settings.naver_weather_url),
        return_exceptions=True,
    )
    errors: dict[str, str] = {}
    for source, result in zip(("kma", "naver_weather"), results):
        if isinstance(result, BaseException):
            errors[source] = f"cannot_connect_{source}"

    if "kma" not in errors:
        try:
            await hass.async_add_executor_job(parse_current_weather, results[0])
        except (TypeError, ValueError):
            errors["kma"] = "invalid_kma_data"
    if "naver_weather" not in errors:
        try:
            numeric, _, _ = await hass.async_add_executor_job(
                parse_naver_weather, results[1]
            )
            if "temperature" not in numeric or "humidity" not in numeric:
                raise ValueError("required Naver weather values are missing")
        except (TypeError, ValueError):
            errors["naver_weather"] = "invalid_naver_weather_data"
    try:
        now = dt_util.now()
        await hass.async_add_executor_job(
            partial(
                parse_weatheri_air,
                weatheri_air_html,
                station=settings.weatheri_air_station,
                fetched_at=now,
                local_tz=now.tzinfo,
            )
        )
    except WeatheriError:
        errors["weatheri_air"] = "invalid_weatheri_air_data"
    return errors


async def _async_fetch_page(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with asyncio.timeout(16):
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                headers=_REQUEST_HEADERS,
            ) as response:
                if response.status != 200:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                    )
                if (
                    response.content_length is not None
                    and response.content_length > _MAX_RESPONSE_BYTES
                ):
                    raise ValueError("response is too large")
                payload = await response.read()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise ConnectionError(str(err)) from err
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise ValueError("response is too large")
    try:
        return payload.decode(response.charset or "utf-8")
    except (LookupError, UnicodeDecodeError) as err:
        raise ValueError("response encoding is invalid") from err


def _detailed_query_location(location_label: str, station: str) -> str:
    """Return a consistent province-and-station Naver place."""
    province = location_label.split(" · ", maxsplit=1)[0]
    if _normalized_place_name(station) == _normalized_place_name(province):
        return province
    return f"{province} {station}"


def _rank_stations(location_label: str, stations: tuple[str, ...]) -> tuple[str, ...]:
    """Place a station matching the forecast location first when available."""
    parts = location_label.split(" · ", maxsplit=1)
    if len(parts) == 1:
        return stations
    wanted = _normalized_place_name(parts[1])
    return tuple(
        sorted(
            stations,
            key=lambda station: _normalized_place_name(station) != wanted,
        )
    )


def _normalized_place_name(value: str) -> str:
    """Normalize common Korean administrative suffixes for matching."""
    normalized = value.replace(" ", "")
    for suffix in ("특별자치시", "광역시", "특별시", "시", "군", "구"):
        if len(normalized) > 2 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized
