"""KMA location resolution and current-weather parsing."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .catalog import ForecastLocation

KMA_ZONE_URL = "https://www.weather.go.kr/w/rest/zone/dong.do"
_REQUEST_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.weather.go.kr/w/index.do",
    "User-Agent": "Home Assistant Korea Weather Fusion",
    "X-Requested-With": "XMLHttpRequest",
}
_WIDE_NAMES = {
    "강원": ("강원특별자치도", "강원도"),
    "경기": ("경기도",),
    "경남": ("경상남도",),
    "경북": ("경상북도",),
    "광주": ("전남광주통합특별시", "광주광역시"),
    "대구": ("대구광역시",),
    "대전": ("대전광역시",),
    "부산": ("부산광역시",),
    "서울": ("서울특별시",),
    "세종": ("세종특별자치시",),
    "울산": ("울산광역시",),
    "인천": ("인천광역시",),
    "전남": ("전남광주통합특별시", "전라남도"),
    "전북": ("전북특별자치도", "전라북도"),
    "제주": ("제주특별자치도", "제주도"),
    "충남": ("충청남도",),
    "충북": ("충청북도",),
}
_NAME_SUFFIXES = (
    "특별자치도",
    "특별자치시",
    "광역시",
    "특별시",
    "도",
    "시",
    "군",
    "구",
)


class KmaError(Exception):
    """Base error for KMA onboarding or parsing."""


class KmaConnectionError(KmaError):
    """Raised when KMA cannot be reached."""


class KmaLocationError(KmaError):
    """Raised when a catalog location cannot be resolved."""


@dataclass(frozen=True, slots=True)
class KmaZone:
    """One KMA administrative zone."""

    code: str
    name: str
    latitude: float
    longitude: float
    level: int


@dataclass(frozen=True, slots=True)
class ResolvedKmaLocation:
    """Resolved KMA zone and whether a city-level match was found."""

    zone: KmaZone
    wide_zone: KmaZone
    exact_city_match: bool


async def async_resolve_location(
    session: aiohttp.ClientSession, location: ForecastLocation
) -> ResolvedKmaLocation:
    """Resolve a Weatheri catalog location through KMA's zone hierarchy."""
    parts = location.label.split(" · ", maxsplit=1)
    wide_key = parts[0]
    expected_wide_names = _WIDE_NAMES.get(wide_key)
    if expected_wide_names is None:
        raise KmaLocationError(f"Unsupported province label: {wide_key}")

    wide_zones = await async_fetch_zones(session, "WIDE")
    wide = next((zone for zone in wide_zones if zone.name in expected_wide_names), None)
    if wide is None:
        raise KmaLocationError(
            f"KMA province was not found: {', '.join(expected_wide_names)}"
        )
    if len(parts) == 1:
        return ResolvedKmaLocation(wide, wide, exact_city_match=True)

    city_zones = await async_fetch_zones(session, "CITY", wide_code=wide.code)
    wanted = _normalized_place_name(parts[1])
    city = next(
        (zone for zone in city_zones if _place_name_matches(zone.name, wanted)),
        None,
    )
    if city is None:
        return ResolvedKmaLocation(wide, wide, exact_city_match=False)
    return ResolvedKmaLocation(city, wide, exact_city_match=True)


async def async_refine_with_station(
    session: aiohttp.ClientSession,
    resolved: ResolvedKmaLocation,
    station: str,
) -> ResolvedKmaLocation:
    """Use the chosen station when it matches a KMA city-level area."""
    wanted = _normalized_place_name(station)
    if _place_name_matches(resolved.zone.name, wanted):
        return resolved
    city_zones = await async_fetch_zones(
        session, "CITY", wide_code=resolved.wide_zone.code
    )
    city = next(
        (zone for zone in city_zones if _place_name_matches(zone.name, wanted)),
        None,
    )
    if city is None:
        return resolved
    return ResolvedKmaLocation(city, resolved.wide_zone, exact_city_match=True)


async def async_fetch_zones(
    session: aiohttp.ClientSession,
    zone_type: str,
    *,
    wide_code: str = "",
) -> list[KmaZone]:
    """Fetch and validate KMA province or city zones."""
    params = {
        "type": zone_type,
        "wideCode": wide_code,
        "cityCode": "",
        "keyword": "",
        "keywordStart": "",
        "keywordEnd": "",
    }
    try:
        async with asyncio.timeout(16):
            async with session.get(
                KMA_ZONE_URL,
                params=params,
                headers=_REQUEST_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    raise KmaConnectionError(f"KMA returned HTTP {response.status}")
                payload = await response.json(content_type=None)
    except KmaError:
        raise
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        raise KmaConnectionError(f"Unable to load KMA locations: {err}") from err
    if not isinstance(payload, list):
        raise KmaLocationError("KMA location response is not a list")
    try:
        zones = [_zone_from_mapping(item) for item in payload]
    except (KeyError, TypeError, ValueError) as err:
        raise KmaLocationError("KMA location response is invalid") from err
    if not zones:
        raise KmaLocationError("KMA returned no locations")
    return zones


def parse_current_weather(html: str) -> dict[str, float]:
    """Extract current values from a weather.go.kr rendered fragment."""
    return parse_current_fields(html)[0]


def parse_current_fields(html: str) -> tuple[dict[str, float], dict[str, str]]:
    """Keep usable fields when another observation is missing or malformed."""
    patterns = {
        "temperature": r'<span class="tmp">\s*([-+]?\d+(?:\.\d+)?)',
        "humidity": (
            r'<span class="lbl ic-hm".*?</span>\s*'
            r'<span class="val">\s*([-+]?\d+(?:\.\d+)?)'
        ),
        "wind_speed": (
            r'<span class="lbl ic-wind".*?</span>\s*'
            r'<span class="val">.*?([-+]?\d+(?:\.\d+)?)\s*'
            r'<small class="unit">km/h'
        ),
    }
    limits = {
        "temperature": (-50, 60),
        "humidity": (0, 100),
        "wind_speed": (0, 500),
        "pm10": (0, 2000),
        "pm25": (0, 2000),
    }
    values, errors = {}, {}
    soup = BeautifulSoup(html, "html.parser")
    air = {}
    for key in ("pm10", "pm25"):
        label = soup.select_one(f'[data-air-type="{key}"]')
        container = label.find_parent("strong") if label else None
        node = container.select_one(".air-lvv") if container else None
        if node:
            air[key] = node.get_text(strip=True)
    # Older fragments contain exactly two cells in PM2.5/PM10 order.
    # Preserve missing cells; never infer positions from only numeric matches.
    nodes = soup.select(".air-lvv")
    if not soup.select("[data-air-type]") and len(nodes) == 2:
        air = {
            key: node.get_text(strip=True) for key, node in zip(("pm25", "pm10"), nodes)
        }
    for key, (low, high) in limits.items():
        try:
            value = (
                _extract_number(html, patterns[key])
                if key in patterns
                else float(air.get(key, ""))
            )
            if not low <= value <= high:
                raise ValueError("out_of_range")
            values[key] = round(value / 3.6, 1) if key == "wind_speed" else value
        except ValueError:
            errors[key] = f"missing_or_invalid:{key}"
    if not values:
        raise ValueError("missing_pattern:no_current_values")
    return values, errors


def _zone_from_mapping(value: dict[str, Any]) -> KmaZone:
    code = str(value["code"])
    name = str(value["name"]).strip()
    if not code.isdigit() or len(code) != 10 or not name:
        raise ValueError("invalid KMA zone")
    return KmaZone(
        code=code,
        name=name,
        latitude=float(value["lat"]),
        longitude=float(value["lon"]),
        level=int(value["level"]),
    )


def _normalized_place_name(value: str) -> str:
    normalized = value.replace(" ", "")
    for suffix in _NAME_SUFFIXES:
        if len(normalized) > 2 and normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _place_name_matches(candidate: str, wanted: str) -> bool:
    """Match exact areas and KMA city names subdivided into districts."""
    normalized = _normalized_place_name(candidate)
    return normalized == wanted or normalized.startswith(f"{wanted}시")


def _extract_number(html: str, pattern: str) -> float:
    match = re.search(pattern, html, flags=re.DOTALL)
    if not match:
        raise ValueError(f"missing_pattern:{pattern}")
    return float(match.group(1))
