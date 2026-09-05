"""Regression coverage for dated forecasts, setup review and partial failures."""

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.util import dt as dt_util
from test_configuration import TEST_CONFIG
from test_fusion import TEST_SETTINGS
from test_fusion import manager as healthy_manager

from custom_components.weather_fusion.config_flow import (
    WeatherFusionConfigFlow,
    WeatherFusionOptionsFlow,
    _input_errors,
)
from custom_components.weather_fusion.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.weather_fusion.fusion import (
    WeatherFusionEngine,
    WeatherFusionManager,
)
from custom_components.weather_fusion.http import MAX_RESPONSE_BYTES, async_fetch_page
from custom_components.weather_fusion.kma import parse_current_fields
from custom_components.weather_fusion.naver import parse_weather_snapshot
from custom_components.weather_fusion.onboarding import (
    ValidationReport,
    async_finalize_guided_values,
    async_validate_sources,
)
from custom_components.weather_fusion.source import (
    KOREA_TZ,
    DailyForecast,
    SourceSnapshot,
)
from custom_components.weather_fusion.weather import WeatherFusionWeather
from custom_components.weather_fusion.weatheri import parse_air, parse_forecast

NOW = datetime(2026, 9, 5, 12, 15, tzinfo=KOREA_TZ)


def naver_html(day="9.05.", tomorrow="9.06.", temperature="31.8"):
    hours = "".join(
        f'<li data-day="{marker}"><dl><dt class="time">{label}</dt>'
        f'<dd class="weather_box"><i class="wt_icon ico_wt1"><span>비</span></i></dd>'
        f'<dd class="degree_point"><span class="num">{20 + index / 10}°</span>'
        "</dd></dl></li>"
        for index, (marker, label) in enumerate(
            [("today", f"{h}시") for h in range(13, 24)]
            + [("tomorrow", "내일"), ("", "01시"), ("", "02시"), ("", "03시")]
        )
    )
    return f"""<div class="_today"><div class="weather_graphic">
      <div class="weather_main"><i class="wt_icon ico_wt1"><span>맑음</span></i></div>
      <div class="temperature_text"><strong>{temperature}°</strong></div></div>
      <div class="temperature_info"><dl><div></div><div><dd>50%</dd></div>
      <div><dd>1.5m/s</dd></div></dl></div></div>
      <ul><li class="week_item today"><span class="date">{day}</span>
      <span class="highest">32°</span><span class="lowest">20°</span></li>
      <li class="week_item"><span class="date">{tomorrow}</span>
      <span class="highest">28°</span><span class="lowest">19°</span></li></ul>
      <div class="graph_inner _hourly_weather"><ul>{hours}</ul></div>"""


def air_html(pm10="", pm25="9", stamp="26.09.05 12:00"):
    headers = (
        "지역",
        "PM10",
        "PM2.5",
        "오존",
        "이산화질소",
        "일산화탄소",
        "아황산가스",
        "대기통합지수",
    )
    values = ("종로구", pm10, pm25, "0.058", "0.007", "0.3", "0.003", "-")
    return (
        f"<p>한국환경공단, {stamp}</p><table><tr>"
        + "".join(f"<th>{v}</th>" for v in headers)
        + "</tr><tr>"
        + "".join(f"<td>{v}</td>" for v in values)
        + "</tr></table>"
    )


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(dt_util, "utcnow", lambda: NOW)


def test_naver_precision_dates_and_real_forecast_times():
    data = parse_weather_snapshot(naver_html(), NOW)
    assert data.numeric["temperature"] == 31.8
    assert data.condition == "sunny"
    assert data.daily[1] == DailyForecast(NOW.date() + timedelta(days=1), 28, 19)
    engine = WeatherFusionEngine({"naver_weather": data}, now=NOW)
    assert engine.forecast("forecast_3h").valid_at == NOW.replace(hour=15, minute=0)
    assert engine.forecast("forecast_12h").valid_at == NOW.replace(
        hour=0, minute=0
    ) + timedelta(days=1)
    assert (
        parse_weather_snapshot(naver_html(temperature="-3.8"), NOW).numeric[
            "temperature"
        ]
        == -3.8
    )


def test_old_relative_labels_cannot_override_dated_fallback():
    old = SourceSnapshot(
        "naver_weather",
        NOW - timedelta(hours=13),
        numeric={"today_high": 28},
        text={"forecast_3h": "비"},
    )
    engine = WeatherFusionEngine(
        {
            "naver_weather": old,
            "weatheri_forecast": SourceSnapshot(
                "weatheri_forecast", NOW, numeric={"today_high": 33}
            ),
        },
        now=NOW,
    )
    assert engine.metric("today_high").value == 33
    assert engine.forecast("forecast_3h").value is None


def test_old_http_success_does_not_refresh_current_observations():
    snapshot = parse_weather_snapshot(naver_html(day="9.04.", tomorrow="9.05."), NOW)
    engine = WeatherFusionEngine({"naver_weather": snapshot}, now=NOW)
    assert engine.metric("temperature").value is None
    assert snapshot.condition is None
    assert engine.metric("today_high").value == 28


def test_status_distinguishes_selected_cache_from_optional_source_failure(frozen):
    manager = healthy_manager()
    assert manager.status() == "fresh"
    manager._naver_snapshots["naver_air"] = SourceSnapshot("naver_air", None)
    manager._naver_last_error["naver_air"] = "no_values"
    assert manager.status() == "fresh"
    manager._weatheri_last_error["weatheri_forecast"] = "temporarily unavailable"
    assert manager.status() == "degraded"
    manager._naver_last_error["naver_weather"] = "temporarily unavailable"
    assert manager.status() == "cached"
    manager._naver_snapshots["naver_weather"] = replace(
        manager._naver_snapshots["naver_weather"], hourly=()
    )
    assert manager.status() == "degraded"
    empty = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
    )
    assert empty.status() == "unavailable"


def test_midnight_reprojects_tomorrow_and_expires_elapsed_slots():
    data = parse_weather_snapshot(naver_html(), NOW)
    after = NOW.replace(hour=0, minute=15) + timedelta(days=1)
    engine = WeatherFusionEngine({"naver_weather": data}, now=after)
    assert engine.metric("today_high").value == 28
    assert engine.metric("tomorrow_high").value is None
    assert engine.forecast("forecast_3h").valid_at == after.replace(hour=3, minute=0)
    assert engine.forecast("forecast_6h").value is None


def test_stale_200_page_keeps_source_dates_and_year_rollover():
    data = parse_weather_snapshot(naver_html(day="9.03.", tomorrow="9.04."), NOW)
    engine = WeatherFusionEngine({"naver_weather": data}, now=NOW)
    assert engine.metric("today_high").value is None
    assert engine.forecast("forecast_3h").value is None
    new_year = NOW.replace(year=2026, month=12, day=31)
    data = parse_weather_snapshot(naver_html(day="12.31.", tomorrow="1.01."), new_year)
    assert data.daily[1].day.year == 2027
    assert data.hourly[-1].time.year == 2027


def test_weatheri_empty_cells_never_shift_measurements():
    values = parse_air(
        air_html(), station="종로구", fetched_at=NOW, local_tz=KOREA_TZ
    ).measurements
    assert values["pm10"] is None
    assert values["pm25"] == 9
    assert values["ozone"] == 0.058


def test_weatheri_invalid_optional_field_does_not_discard_pm():
    values = parse_air(
        air_html("20").replace("0.058", "점검"),
        station="종로구",
        fetched_at=NOW,
        local_tz=KOREA_TZ,
    ).measurements
    assert values["pm10"] == 20 and values["pm25"] == 9
    assert values["ozone"] is None


def test_weatheri_real_merged_header_and_icon_columns():
    headers = (
        "PM10",
        "PM2.5",
        "오존",
        "이산화질소",
        "일산화탄소",
        "아황산가스",
        "대기통합지수",
    )
    values = ("", "9", "0.041", "0.005", "0.2", "0.002", "60")
    html = "<p>한국환경공단, 26.09.05 12:00</p><table><tr><td>지역</td>"
    html += "".join(f'<td colspan="2">{key}</td>' for key in headers)
    html += "</tr><tr><td>종로구</td>"
    html += "".join(f'<td><img src="w1.gif"></td><td>{value}</td>' for value in values)
    html += "</tr></table>"
    result = parse_air(html, station="종로구", fetched_at=NOW, local_tz=KOREA_TZ)
    assert result.measurements == {
        "pm10": None,
        "pm25": 9,
        "ozone": 0.041,
        "nitrogen_dioxide": 0.005,
        "carbon_monoxide": 0.2,
        "sulfur_dioxide": 0.002,
        "aqi": 60,
    }


def test_weatheri_leap_day():
    now = NOW.replace(year=2028, month=2, day=29)
    html = """<table><tr><td>02월 29일</td><td>03월 01일</td></tr><tr>
        <td onclick='showthree("1")'>10°C 1°C</td>
        <td onclick='showthree("2")'>11°C 2°C</td></tr></table>"""
    assert (
        parse_forecast(
            html, location="서울", current_date=now.date(), fetched_at=now
        ).today_high
        == 10
    )


def test_kma_partial_observations_preserve_semantic_pm_labels():
    html = """<span class="tmp">22.5</span>
      <strong><span class="air-lvv">-</span><a data-air-type="pm25"></a></strong>
      <strong><span class="air-lvv">17</span><a data-air-type="pm10"></a></strong>
      <strong><span class="air-lvv">.05</span><a data-air-type="o3"></a></strong>"""
    values, errors = parse_current_fields(html)
    assert values == {"temperature": 22.5, "pm10": 17}
    assert "pm25" in errors and "humidity" in errors


def flow_hass(entry=None):
    return SimpleNamespace(
        config=SimpleNamespace(language="ko"),
        config_entries=SimpleNamespace(
            async_get_known_entry=lambda _: entry, async_get_entry=lambda _: entry
        ),
    )


def test_options_keeps_station_and_fine_grained_weather_overrides(monkeypatch, frozen):
    current = {
        **TEST_CONFIG,
        "location_id": "1100000000",
        "weatheri_air_station": "강남구",
    }
    entry = SimpleNamespace(data=current, options={})
    guided = SimpleNamespace(
        values={**current, "kma_code": "1100000000"},
        stations=("종로구", "강남구"),
        location_label="서울",
        kma_location_label="서울특별시",
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.config_flow.async_prepare_guided_setup",
        AsyncMock(return_value=guided),
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.config_flow.async_validate_sources",
        AsyncMock(
            return_value=ValidationReport(
                available={"kma": {"temperature"}}, checked_at=NOW
            )
        ),
    )

    async def run():
        flow = WeatherFusionOptionsFlow()
        flow.hass = flow_hass(entry)
        flow.handler = "entry"
        form = await flow.async_step_init({"location_id": "1100000000"})
        assert form["data_schema"]({})["weatheri_air_station"] == "강남구"
        review = await flow.async_step_air_station({"weatheri_air_station": "종로구"})
        assert review["step_id"] == "review"
        assert flow._pending["kma_code"] == current["kma_code"]
        result = await flow.async_step_review({"action": "save"})
        assert result["data"]["weatheri_air_station"] == "종로구"

    asyncio.run(run())


def test_station_only_change_preserves_weather_location():
    data = {**TEST_CONFIG, "naver_weather_query": "경남 김해 날씨"}
    result = asyncio.run(
        async_finalize_guided_values(None, SimpleNamespace(values=data), "창원시")
    )
    assert result["naver_weather_query"] == data["naver_weather_query"]
    assert result["kma_code"] == data["kma_code"]


@pytest.mark.parametrize("code", ["1", "0000000000", "１２３４５６７８９０", "invalid"])
def test_manual_invalid_codes_block_before_fetch(code):
    assert _input_errors({**TEST_CONFIG, "kma_code": code}) == {
        "kma_code": "invalid_code"
    }


def test_manual_setup_requires_review_and_limited_consent(monkeypatch, frozen):
    report = ValidationReport(
        {"kma": {"temperature"}}, {"naver_weather": "missing_data"}, NOW
    )
    check = AsyncMock(return_value=report)
    monkeypatch.setattr(
        "custom_components.weather_fusion.config_flow.async_validate_sources", check
    )

    async def run():
        flow = WeatherFusionConfigFlow()
        flow.context = {"source": "user"}
        flow.hass = flow_hass()
        bad = await flow.async_step_advanced({**TEST_CONFIG, "kma_code": "1"})
        assert bad["errors"]["kma_code"] == "invalid_code"
        check.assert_not_awaited()
        assert (await flow.async_step_advanced(TEST_CONFIG))["step_id"] == "review"
        result = await flow.async_step_review({"action": "save"})
        assert result["errors"]["base"] == "limited_confirmation"
        result = await flow.async_step_review({"action": "save", "allow_limited": True})
        assert result["type"] == "create_entry"

    asyncio.run(run())


def test_reconfigure_clears_old_location_options_without_changing_identity(frozen):
    entry = SimpleNamespace(
        data=TEST_CONFIG, options={"kma_code": "1111111111", "other": True}
    )

    async def run():
        flow = WeatherFusionConfigFlow()
        flow.context = {"source": "reconfigure", "entry_id": "same-entry"}
        flow.hass = flow_hass(entry)
        flow._pending = {**TEST_CONFIG, "kma_code": "2222222222"}
        flow._report = ValidationReport({"kma": {"temperature"}}, checked_at=NOW)
        flow.hass.config_entries.async_update_entry = Mock()
        assert (await flow.async_step_review({"action": "save"}))["type"] == "abort"
        args = flow.hass.config_entries.async_update_entry.call_args
        assert args.args[0] is entry
        assert args.kwargs["options"] == {"other": True}
        assert args.kwargs["data"]["kma_code"] == "2222222222"

    asyncio.run(run())


def test_no_usable_sources_cannot_be_saved_even_with_consent(frozen):
    async def run():
        flow = WeatherFusionConfigFlow()
        flow.hass = flow_hass()
        flow.context = {"source": "user"}
        flow._pending = TEST_CONFIG
        flow._report = ValidationReport({}, {"kma": "cannot_validate"}, NOW)
        result = await flow.async_step_review({"action": "save", "allow_limited": True})
        assert result["errors"]["base"] == "no_usable_sources"

    asyncio.run(run())


def test_review_names_missing_capabilities_and_refreshes_expired_checks(
    monkeypatch, frozen
):
    initial = ValidationReport(
        {"kma": {"temperature"}}, {"kma": "missing_data"}, NOW - timedelta(minutes=6)
    )
    refreshed = ValidationReport({"kma": {"temperature"}}, checked_at=NOW)
    check = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(
        "custom_components.weather_fusion.config_flow.async_validate_sources", check
    )

    async def run():
        flow = WeatherFusionConfigFlow()
        flow.hass = flow_hass()
        flow.context = {"source": "user"}
        flow._pending = TEST_CONFIG
        flow._report = initial
        form = await flow.async_step_review()
        assert "습도" in form["description_placeholders"]["kma"]
        assert "풍속" in form["description_placeholders"]["kma"]
        result = await flow.async_step_review({"action": "save", "allow_limited": True})
        assert result["errors"]["base"] == "checks_refreshed"
        check.assert_awaited_once_with(flow.hass, TEST_CONFIG)
        assert (await flow.async_step_review({"action": "save"}))[
            "type"
        ] == "create_entry"

    asyncio.run(run())


def test_retry_only_rechecks_failed_sources(monkeypatch, frozen):
    async def executor(fn, *args):
        return fn(*args)

    previous = ValidationReport(
        {
            "kma": {"temperature", "humidity", "wind_speed"},
            "naver_weather": {"temperature", "humidity", "daily"},
            "naver_air": {"pm10", "pm25"},
            "weatheri_forecast": {"daily"},
            "weatheri_air": set(),
        },
        {"weatheri_air": "missing_data"},
        NOW - timedelta(minutes=4),
    )
    fetch = AsyncMock(return_value=air_html("12", "8"))
    other_fetch = AsyncMock(side_effect=AssertionError("Healthy source fetched again"))
    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_get_clientsession",
        lambda _: object(),
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_fetch_html", fetch
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_fetch_page", other_fetch
    )
    result = asyncio.run(
        async_validate_sources(
            SimpleNamespace(async_add_executor_job=executor), TEST_CONFIG, previous
        )
    )
    assert result.complete and result.available["weatheri_air"] >= {"pm10", "pm25"}
    assert fetch.await_count == 1 and other_fetch.await_count == 0
    assert result.checked_at == previous.checked_at


def test_shared_validation_detects_missing_and_stale_air(monkeypatch, frozen):
    async def execute(fn, *args):
        return fn(*args)

    async def fetch(_session, url):
        if "current-weather" in url:
            return '<span class="tmp">22.5</span>'
        if "special05" in url:
            return air_html("-", "-", "26.09.05 01:00")
        return naver_html()

    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_get_clientsession",
        lambda _: object(),
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_fetch_page", fetch
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.onboarding.async_fetch_html", fetch
    )
    result = asyncio.run(
        async_validate_sources(
            SimpleNamespace(async_add_executor_job=execute), TEST_CONFIG
        )
    )
    assert result.errors["weatheri_air"] == "stale_data"
    assert result.errors["kma"] == "missing_data"
    assert not result.complete and result.usable
    assert "naver_weather" not in result.errors


def test_native_weather_never_invents_temperature_or_current_condition(frozen):
    manager = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
    )
    manager._naver_snapshots["naver_weather"] = parse_weather_snapshot(
        naver_html(), NOW
    )
    entity = WeatherFusionWeather(manager)
    assert entity.condition == "sunny" and entity.native_temperature == 31.8
    assert entity.should_poll is False
    assert asyncio.run(entity.async_forecast_daily())[0]["native_temperature"] == 32
    points = asyncio.run(entity.async_forecast_hourly())
    assert points and all(
        datetime.fromisoformat(item["datetime"]) > NOW for item in points
    )
    snap = manager._naver_snapshots["naver_weather"]
    manager._naver_snapshots["naver_weather"] = replace(
        snap,
        condition=None,
        hourly=tuple(replace(p, temperature=None) for p in snap.hourly),
    )
    assert entity.condition is None
    assert asyncio.run(entity.async_forecast_hourly()) == []


def test_diagnostics_never_exports_location_or_error_urls(frozen):
    manager = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
    )
    manager._naver_last_error["naver_weather"] = "ClientError secret-location-url"
    result = asyncio.run(
        async_get_config_entry_diagnostics(
            SimpleNamespace(data={"weather_fusion": {"entry": manager}}),
            SimpleNamespace(entry_id="entry", version=3),
        )
    )
    encoded = json.dumps(result, ensure_ascii=False)
    assert (
        "secret-location" not in encoded
        and "서울" not in encoded
        and "1111051500" not in encoded
    )


def test_runtime_parser_is_offloaded(monkeypatch, frozen):
    executed = []

    async def execute(fn, *args):
        executed.append(fn)
        return fn(*args)

    monkeypatch.setattr(
        "custom_components.weather_fusion.fusion.async_get_clientsession",
        lambda _: object(),
    )
    monkeypatch.setattr(
        "custom_components.weather_fusion.fusion.async_fetch_page",
        AsyncMock(return_value=naver_html()),
    )
    manager = WeatherFusionManager(
        SimpleNamespace(async_add_executor_job=execute),
        weatheri_store=SimpleNamespace(),
        settings=TEST_SETTINGS,
    )
    asyncio.run(manager.async_update_naver())
    assert parse_weather_snapshot in executed
    assert manager.metric("temperature").value == 31.8


def test_streaming_limit_stops_before_reading_whole_response():
    read = []

    async def chunks(_size):
        for i in range(100):
            read.append(i)
            yield b"x" * (64 * 1024)

    class Response:
        content_length = None
        content = SimpleNamespace(iter_chunked=chunks)

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    session = SimpleNamespace(get=lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="response_too_large"):
        asyncio.run(async_fetch_page(session, "https://example.invalid"))
    assert len(read) == MAX_RESPONSE_BYTES // (64 * 1024) + 1


def test_weatheri_overlap_and_unload_cancel_inflight(monkeypatch):
    async def run():
        entered = asyncio.Event()
        calls = []

        async def fetch():
            calls.append(1)
            entered.set()
            await asyncio.Event().wait()

        manager = WeatherFusionManager(
            SimpleNamespace(async_create_task=asyncio.create_task),
            weatheri_store=SimpleNamespace(),
            settings=TEST_SETTINGS,
        )
        monkeypatch.setattr(manager, "_async_update_weatheri", fetch)
        manager._spawn(manager.async_update_weatheri())
        await entered.wait()
        await manager.async_update_weatheri()
        assert len(calls) == 1
        tasks = tuple(manager._tasks)
        manager.async_stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert all(task.cancelled() for task in tasks)

    asyncio.run(run())
