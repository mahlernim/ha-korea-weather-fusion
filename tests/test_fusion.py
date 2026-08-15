"""Unit tests for Korea Weather Fusion selection and freshness."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.weather_fusion.configuration import WeatherFusionSettings
from custom_components.weather_fusion.fusion import (
    KmaSample,
    WeatherFusionEngine,
    WeatherFusionManager,
)
from custom_components.weather_fusion.naver import parse_air, parse_weather
from custom_components.weather_fusion.source import SourceSnapshot
from custom_components.weather_fusion.weatheri import (
    WeatheriAir,
    WeatheriError,
    WeatheriForecast,
)
from custom_components.weather_fusion.weatheri import (
    parse_air as parse_weatheri_air,
)
from custom_components.weather_fusion.weatheri import (
    parse_forecast as parse_weatheri_forecast,
)

KMA_VALUES = {
    "temperature": 22.0,
    "humidity": 70.0,
    "wind_speed": 1.5,
    "pm10": 25.0,
    "pm25": 12.0,
}
NAVER_WEATHER_NUMERIC = {
    "temperature": 20.0,
    "humidity": 60.0,
    "wind_speed": 2.5,
    "today_high": 28.0,
    "today_low": 18.0,
    "tomorrow_high": 29.0,
    "tomorrow_low": 19.0,
}
NAVER_WEATHER_TEXT = {
    "uv": "높음",
    "wind_direction": "남서풍",
    "forecast_3h": "맑음",
    "forecast_6h": "흐림",
    "forecast_9h": "비",
    "forecast_12h": "맑음",
}
NAVER_AIR = {"pm10": 30.0, "pm25": 15.0}
TEST_SETTINGS = WeatherFusionSettings(
    kma_code="1111051500",
    naver_weather_query="서울 날씨",
    naver_air_query="서울 종로구 미세먼지",
    weatheri_forecast_rid="1100000000",
    weatheri_forecast_group="1",
    weatheri_location="서울",
    weatheri_air_region_code="01",
    weatheri_air_station="종로구",
)


def manager(
    kma_values: dict[str, float] | None = KMA_VALUES,
    kma_age_minutes: int = 0,
    naver_age_minutes: int = 0,
) -> WeatherFusionManager:
    fusion = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
    )
    naver_reported = dt_util.utcnow() - timedelta(minutes=naver_age_minutes)
    fusion._naver_snapshots = {
        "naver_weather": SourceSnapshot(
            group="naver_weather",
            last_reported=naver_reported,
            numeric=NAVER_WEATHER_NUMERIC,
            text=NAVER_WEATHER_TEXT,
        ),
        "naver_air": SourceSnapshot(
            group="naver_air",
            last_reported=naver_reported,
            numeric=NAVER_AIR,
        ),
    }
    if kma_values is not None:
        reported = dt_util.utcnow() - timedelta(minutes=kma_age_minutes)
        fusion._kma_last_success = reported
        fusion._kma_samples = {
            key: KmaSample(value=value, last_reported=reported)
            for key, value in kma_values.items()
        }
    now = dt_util.now()
    fusion._weatheri_forecast = WeatheriForecast(
        "서울", now.date(), now, 27.0, 17.0, 30.0, 20.0
    )
    fusion._weatheri_air = WeatheriAir(
        "종로구",
        now,
        now,
        {
            "pm10": 20.0,
            "pm25": 10.0,
            "ozone": 0.05,
            "nitrogen_dioxide": 0.01,
            "carbon_monoxide": 0.3,
            "sulfur_dioxide": 0.003,
            "aqi": 50.0,
        },
    )
    fusion._weatheri_last_success = {
        "weatheri_forecast": now,
        "weatheri_air": now,
    }
    return fusion


def test_mean_priority_and_kma_wind_conversion() -> None:
    fusion = manager()
    assert fusion.metric("temperature").value == 21.0
    assert fusion.metric("temperature").selected_sources == ("naver", "weather_go_kr")
    assert fusion.metric("pm10").value == 20.0
    wind = fusion.metric("wind_speed")
    assert wind.value == 2.0
    assert wind.eligible_sources == {"naver": 2.5, "weather_go_kr": 1.5}


def test_missing_direct_kma_sample_falls_back_to_naver() -> None:
    result = manager(kma_values=None).metric("temperature")
    assert result.value == 20.0
    assert "weather_go_kr" in result.rejected_sources


def test_kma_html_parser_converts_wind_and_maps_air_values() -> None:
    html = """
    <span class="tmp">22.5</span>
    <span class="lbl ic-hm">Humidity</span><span class="val"> 71
    <span class="lbl ic-wind">Wind</span><span class="val">W 5.4
      <small class="unit">km/h</small>
    <span class="air-lvv"> 12 </span><span class="air-lvv"> 25 </span>
    """
    assert manager()._parse_kma_html(html) == {
        "temperature": 22.5,
        "humidity": 71.0,
        "wind_speed": 1.5,
        "pm10": 25.0,
        "pm25": 12.0,
    }


def test_kma_html_parser_rejects_incomplete_response() -> None:
    with pytest.raises(ValueError, match="missing_pattern"):
        manager()._parse_kma_html("<html></html>")


def test_stale_naver_source_group_uses_fresh_kma() -> None:
    result = manager(naver_age_minutes=300).metric("wind_speed")
    assert result.value == 1.5
    assert result.selected_sources == ("weather_go_kr",)
    assert result.rejected_sources["naver"].startswith("source_stale:naver_weather")


def test_weatheri_gate_and_pm_fallback() -> None:
    fusion = manager()
    fusion._weatheri_air = None
    result = fusion.metric("pm10")
    assert result.value == 25.0
    assert result.selected_sources == ("weather_go_kr",)


def test_stale_kma_falls_back_to_naver() -> None:
    fusion = manager(kma_age_minutes=300)
    wind = fusion.metric("wind_speed")
    assert wind.value == 2.5
    assert wind.selected_sources == ("naver",)
    assert wind.rejected_sources["weather_go_kr"].startswith(
        "source_stale:weather_go_kr"
    )


def test_forecast_passthrough_and_health_sensors() -> None:
    fusion = manager()
    assert fusion.forecast("forecast_9h").value == "비"
    assert fusion.health()[0] is True
    assert fusion.forecast_health()[0] is True
    broken = manager()
    broken._naver_snapshots["naver_weather"] = SourceSnapshot(
        group="naver_weather",
        last_reported=dt_util.utcnow(),
        numeric=NAVER_WEATHER_NUMERIC,
        text={
            key: value
            for key, value in NAVER_WEATHER_TEXT.items()
            if key != "forecast_12h"
        },
        value_errors={"forecast_12h": "state:unavailable"},
    )
    assert broken.health()[0] is True
    assert broken.forecast_health()[0] is False


def test_manager_exposes_all_internal_source_snapshots() -> None:
    snapshots = manager().source_snapshots()
    assert snapshots["naver_weather"].numeric["temperature"] == 20.0
    assert snapshots["weatheri_air"].numeric["pm10"] == 20.0
    assert snapshots["weatheri_air"].numeric["pm25"] == 10.0
    assert snapshots["weatheri_forecast"].numeric["today_high"] == 27.0
    assert snapshots["weather_go_kr"].numeric == KMA_VALUES


def test_engine_fuses_snapshots_without_home_assistant_entity_ids() -> None:
    reported = dt_util.utcnow()
    engine = WeatherFusionEngine(
        {
            "naver_weather": SourceSnapshot(
                group="naver_weather",
                last_reported=reported,
                numeric={
                    "temperature": 20.0,
                    "today_high": 28.0,
                },
                text={"forecast_3h": "맑음"},
            ),
            "weatheri_air": SourceSnapshot(
                group="weatheri_air",
                last_reported=reported,
                numeric={"pm10": 20.0},
            ),
            "weather_go_kr": SourceSnapshot(
                group="weather_go_kr",
                last_reported=reported,
                numeric={"temperature": 22.0, "pm10": 25.0},
            ),
        },
        now=reported,
    )

    temperature = engine.metric("temperature")
    assert temperature.value == 21.0
    assert temperature.selected_sources == ("naver", "weather_go_kr")
    assert engine.metric("pm10").selected_sources == ("weatheri",)
    assert engine.metric("today_high").selected_sources == ("naver",)
    assert engine.forecast("forecast_3h").value == "맑음"


def test_naver_parsers_preserve_existing_multiscrape_semantics() -> None:
    hourly = "".join(
        f'<li><dl><dd class="weather_box"><i><span>{value}</span></i></dd></dl></li>'
        for value in (
            "맑음",
            "맑음",
            "흐림",
            "흐림",
            "흐림",
            "비",
            "비",
            "비",
            "눈",
            "눈",
            "눈",
            "맑음",
        )
    )
    html = f"""
    <div class="_today">
      <div class="weather_graphic"><div class="temperature_text">
        <strong>현재 온도 31.8°</strong>
      </div></div>
      <div class="temperature_info"><dl>
        <div></div><div><dd>51%</dd></div><div><dt>남서풍</dt><dd>2.4m/s</dd></div>
      </dl></div>
    </div>
    <ul><li class="week_item today">
      <span class="lowest">최저 24°</span><span class="highest">최고 30°</span>
    </li><li class="week_item">
      <span class="lowest">최저 23°</span><span class="highest">최고 26°</span>
    </li></ul>
    <div class="report_card_wrap"><ul><li></li><li></li><li>
      <span class="box"><span class="txt">높음</span></span>
    </li></ul></div>
    <div class="graph_inner _hourly_weather"><ul>{hourly}</ul></div>
    """
    numeric, text, errors = parse_weather(html)
    assert errors == {}
    assert numeric == {
        "temperature": 31.0,
        "humidity": 51.0,
        "wind_speed": 2.4,
        "today_high": 30.0,
        "today_low": 24.0,
        "tomorrow_high": 26.0,
        "tomorrow_low": 23.0,
    }
    assert text["forecast_3h"] == "흐림"
    assert text["forecast_6h"] == "비"
    assert text["forecast_9h"] == "눈"
    assert text["forecast_12h"] == "맑음"
    assert parse_air(
        '<li class="_fine_dust"><span class="figure_box _value">20</span></li>'
        '<li class="_ultrafine_dust"><span class="figure_box _value">55</span></li>'
    ) == ({"pm10": 20.0, "pm25": 55.0}, {})


def test_naver_optional_selector_failure_is_field_scoped() -> None:
    numeric, text, errors = parse_weather(
        '<div class="_today"><div class="weather_graphic">'
        '<div class="temperature_text"><strong>현재 온도 31.8°</strong>'
        "</div></div></div>"
    )
    assert numeric == {"temperature": 31.0}
    assert text == {}
    assert errors["uv"] == "missing_selector:uv"
    assert errors["forecast_12h"] == "missing_selector:forecast_12h"


def test_naver_failure_metadata_retains_last_good_snapshot() -> None:
    fusion = manager()
    fusion._naver_last_error["naver_weather"] = "ClientError: temporary"
    snapshot = fusion.source_snapshots()["naver_weather"]
    assert snapshot.numeric["temperature"] == 20.0
    assert snapshot.unavailable_reason is None
    assert snapshot.attributes["last_error"] == "ClientError: temporary"


def test_weatheri_parsers_validate_dates_station_and_all_measurements() -> None:
    tz = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 8, 15, 13, 30, tzinfo=tz)
    forecast_html = """
    <table>
      <tr><td>08월 15일</td><td>08월 16일</td></tr>
      <tr>
        <td onclick='showthree("1")'>30˚C 24˚C</td>
        <td onclick='showthree("2")'>26˚C 23˚C</td>
      </tr>
    </table>
    """
    forecast = parse_weatheri_forecast(
        forecast_html,
        location="서울",
        current_date=date(2026, 8, 15),
        fetched_at=now,
    )
    assert forecast.today_high == 30.0
    assert forecast.tomorrow_low == 23.0

    headers = (
        "지역",
        "미세먼지 (PM10)",
        "초미세먼지 (PM2.5)",
        "오존",
        "이산화질소",
        "일산화탄소",
        "아황산가스",
        "대기통합지수",
    )
    values = ("종로구", "28", "9", "0.058", "0.007", "0.3", "0.003", "74")
    air_html = (
        "<p>한국환경공단, 26.08.15 13:00</p><table><tr>"
        + "".join(f"<th>{value}</th>" for value in headers)
        + "</tr><tr>"
        + "".join(f"<td>{value}</td>" for value in values)
        + "</tr></table>"
    )
    air = parse_weatheri_air(air_html, station="종로구", fetched_at=now, local_tz=tz)
    assert air.measurements == {
        "pm10": 28.0,
        "pm25": 9.0,
        "ozone": 0.058,
        "nitrogen_dioxide": 0.007,
        "carbon_monoxide": 0.3,
        "sulfur_dioxide": 0.003,
        "aqi": 74.0,
    }


def test_weatheri_parser_rejects_wrong_forecast_day() -> None:
    tz = ZoneInfo("Asia/Seoul")
    now = datetime(2026, 8, 15, 13, 30, tzinfo=tz)
    with pytest.raises(WeatheriError, match="Forecast dates"):
        parse_weatheri_forecast(
            """
            <table><tr><td>08월 14일</td><td>08월 15일</td></tr><tr>
              <td onclick='showthree("1")'>30˚C 24˚C</td>
              <td onclick='showthree("2")'>26˚C 23˚C</td>
            </tr></table>
            """,
            location="서울",
            current_date=date(2026, 8, 15),
            fetched_at=now,
        )
