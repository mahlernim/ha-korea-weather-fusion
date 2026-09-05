"""Tests for guided Korean location onboarding."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.weather_fusion import async_migrate_entry
from custom_components.weather_fusion.catalog import LOCATIONS, get_location
from custom_components.weather_fusion.configuration import (
    ADVANCED_LOCATION_ID,
    CONF_LOCATION_ID,
)
from custom_components.weather_fusion.kma import (
    _normalized_place_name,
    _place_name_matches,
    async_refine_with_station,
    async_resolve_location,
)
from custom_components.weather_fusion.onboarding import (
    _rank_stations,
    async_finalize_guided_values,
)


class _Response:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, *, content_type=None):
        return self._payload


class _Session:
    def __init__(self, wide, city):
        self._wide = wide
        self._city = city

    def get(self, _url, *, params, **_kwargs):
        return _Response(self._wide if params["type"] == "WIDE" else self._city)


def _zone(code: str, name: str, level: int) -> dict[str, str]:
    return {
        "code": code,
        "name": name,
        "lat": "35.0",
        "lon": "129.0",
        "level": str(level),
    }


def test_catalog_contains_the_retired_weatheri_location_set() -> None:
    assert len(LOCATIONS) == 172
    assert get_location("1101010100").label == "부산"
    assert len({location.label for location in LOCATIONS.values()}) == len(LOCATIONS)
    assert all(
        location.rid.isdigit()
        and location.forecast_group.isdigit()
        and location.air_region_code.isdigit()
        for location in LOCATIONS.values()
    )


def test_kma_resolution_uses_city_match_and_province_fallback() -> None:
    wide = [
        _zone("4800000000", "경상남도", 1),
        _zone("5000000000", "제주특별자치도", 1),
    ]
    city = [_zone("4825000000", "김해시", 2)]
    resolved = asyncio.run(
        async_resolve_location(_Session(wide, city), get_location("1202010104"))
    )
    assert resolved.zone.code == "4825000000"
    assert resolved.exact_city_match is True

    resolved = asyncio.run(
        async_resolve_location(_Session(wide, city), get_location("1301010102"))
    )
    assert resolved.zone.code == "5000000000"
    assert resolved.exact_city_match is False


def test_station_ranking_does_not_change_weather_query() -> None:
    wide = [_zone("2600000000", "부산광역시", 1)]
    city = [
        _zone("2611000000", "중구", 2),
        _zone("2635000000", "해운대구", 2),
    ]
    resolved = asyncio.run(
        async_resolve_location(_Session(wide, city), get_location("1101010100"))
    )
    refined = asyncio.run(
        async_refine_with_station(_Session(wide, city), resolved, "해운대구")
    )
    assert refined.zone.code == "2635000000"
    values = {"naver_weather_query": "부산 해운대구 날씨", "kma_code": "2635000000"}
    updated = asyncio.run(
        async_finalize_guided_values(None, SimpleNamespace(values=values), "강서구")
    )
    assert updated == {**values, "weatheri_air_station": "강서구"}
    assert _rank_stations("부산 · 해운대", ("강서구", "해운대구", "중구")) == (
        "해운대구",
        "강서구",
        "중구",
    )


def test_station_can_replace_an_initial_city_match() -> None:
    wide = [_zone("4800000000", "경상남도", 1)]
    city = [
        _zone("4812000000", "창원시", 2),
        _zone("4825000000", "김해시", 2),
    ]
    resolved = asyncio.run(
        async_resolve_location(_Session(wide, city), get_location("1202010104"))
    )
    assert resolved.zone.name == "김해시"
    refined = asyncio.run(
        async_refine_with_station(_Session(wide, city), resolved, "창원시")
    )
    assert refined.zone.name == "창원시"


def test_kma_place_matching_preserves_short_names_and_accepts_city_districts() -> None:
    assert _normalized_place_name("양구") == "양구"
    assert _normalized_place_name("완도") == "완도"
    assert _place_name_matches("양구군", "양구")
    assert _place_name_matches("수원시권선구", "수원")
    assert not _place_name_matches("고양시덕양구", "양구")


def test_version_two_entry_migrates_to_advanced_without_changing_selectors() -> None:
    original = {"kma_code": "2600000000", "naver_weather_query": "부산 날씨"}
    entry = SimpleNamespace(version=2, data=original)
    changes = {}

    class ConfigEntries:
        def async_update_entry(self, target, **kwargs):
            assert target is entry
            changes.update(kwargs)

    hass = SimpleNamespace(config_entries=ConfigEntries())
    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert changes["version"] == 3
    assert changes["data"] == {
        **original,
        CONF_LOCATION_ID: ADVANCED_LOCATION_ID,
    }
