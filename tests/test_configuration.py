"""Tests for Korea Weather Fusion configuration."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import voluptuous as vol
from voluptuous_serialize import convert

from custom_components.weather_fusion.config_flow import _config_schema, _input_errors
from custom_components.weather_fusion.configuration import (
    CONF_KMA_CODE,
    CONF_NAVER_AIR_QUERY,
    CONF_NAVER_WEATHER_QUERY,
    CONF_WEATHERI_AIR_REGION_CODE,
    CONF_WEATHERI_AIR_STATION,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_LOCATION,
    WeatherFusionSettings,
    normalize_config,
)
from custom_components.weather_fusion.fusion import WeatherFusionManager
from custom_components.weather_fusion.weatheri import WeatheriForecast

TEST_CONFIG = {
    CONF_KMA_CODE: "1111051500",
    CONF_NAVER_WEATHER_QUERY: "서울 날씨",
    CONF_NAVER_AIR_QUERY: "서울 종로구 미세먼지",
    CONF_WEATHERI_FORECAST_RID: "1100000000",
    CONF_WEATHERI_FORECAST_GROUP: "1",
    CONF_WEATHERI_LOCATION: "서울",
    CONF_WEATHERI_AIR_REGION_CODE: "01",
    CONF_WEATHERI_AIR_STATION: "종로구",
}


def test_default_settings_build_exact_source_parameters() -> None:
    settings = WeatherFusionSettings.from_mapping(TEST_CONFIG)
    assert parse_qs(urlparse(settings.kma_url).query) == {
        "code": [TEST_CONFIG[CONF_KMA_CODE]]
    }
    assert parse_qs(urlparse(settings.naver_weather_url).query)["query"] == [
        TEST_CONFIG[CONF_NAVER_WEATHER_QUERY]
    ]
    assert parse_qs(urlparse(settings.naver_air_url).query)["query"] == [
        TEST_CONFIG[CONF_NAVER_AIR_QUERY]
    ]
    assert parse_qs(urlparse(settings.weatheri_forecast_url).query) == {
        "rid": [TEST_CONFIG[CONF_WEATHERI_FORECAST_RID]],
        "k": [TEST_CONFIG[CONF_WEATHERI_FORECAST_GROUP]],
        "a_name": [TEST_CONFIG[CONF_WEATHERI_LOCATION]],
    }
    assert parse_qs(urlparse(settings.weatheri_air_url).query) == {
        "a": [TEST_CONFIG[CONF_WEATHERI_AIR_REGION_CODE]]
    }


def test_normalize_and_schema_reject_blank_or_non_numeric_codes() -> None:
    assert (
        normalize_config({CONF_NAVER_WEATHER_QUERY: "  서울 날씨  "})[
            CONF_NAVER_WEATHER_QUERY
        ]
        == "서울 날씨"
    )
    schema = _config_schema(TEST_CONFIG)
    invalid = {**TEST_CONFIG, CONF_KMA_CODE: "not-a-code"}
    assert _input_errors(schema(invalid)) == {CONF_KMA_CODE: "invalid_code"}
    invalid = {**TEST_CONFIG, CONF_WEATHERI_AIR_STATION: "   "}
    with pytest.raises(vol.Invalid):
        schema(invalid)


def test_config_schema_is_serializable_by_home_assistant() -> None:
    serialized = convert(_config_schema(TEST_CONFIG))
    assert len(serialized) == 8
    assert {field["name"] for field in serialized} == set(TEST_CONFIG)


def test_weatheri_cache_is_scoped_to_configured_location() -> None:
    now = datetime.now().astimezone()
    cached = WeatheriForecast(
        location="부산",
        source_date=now.date(),
        fetched_at=now,
        today_high=30,
        today_low=20,
        tomorrow_high=29,
        tomorrow_low=19,
    )

    class Store:
        async def async_load(self):
            return {"forecast": cached.as_dict(), "air": None}

    settings = WeatherFusionSettings.from_mapping(
        {
            CONF_WEATHERI_LOCATION: "서울",
            CONF_WEATHERI_AIR_STATION: "종로구",
        }
    )
    manager = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=Store(), settings=settings
    )
    asyncio.run(manager._async_load_weatheri_cache())
    assert manager._weatheri_forecast is None
