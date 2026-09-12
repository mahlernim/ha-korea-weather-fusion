"""Behavioral regressions for multiple locations, setup and refresh lifecycle."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_configuration import TEST_CONFIG
from test_fusion import TEST_SETTINGS
from test_review_regressions import NOW, drive, flow_hass, naver_html

from custom_components.weather_fusion import async_migrate_entry
from custom_components.weather_fusion.config_flow import WeatherFusionConfigFlow
from custom_components.weather_fusion.fusion import WeatherFusionManager
from custom_components.weather_fusion.naver import parse_air, parse_weather_snapshot
from custom_components.weather_fusion.onboarding import (
    GuidedSetupError,
    ValidationReport,
    async_prepare_guided_setup,
)


@pytest.mark.parametrize("value", ["999", "-51", "61"])
def test_naver_out_of_range_current_rejected(value):
    snapshot = parse_weather_snapshot(naver_html(temperature=value), NOW)
    assert "temperature" not in snapshot.numeric
    assert snapshot.value_errors["temperature"] == "out_of_range:temperature"
    assert snapshot.numeric["humidity"] == 50


@pytest.mark.parametrize("value", ["-1", "2001"])
def test_naver_pm_out_of_range_rejected(value):
    values, errors = parse_air(
        f'<li class="_fine_dust"><span class="figure_box _value">{value}</span></li>'
    )
    assert "pm10" not in values
    assert errors["pm10"] == "out_of_range:pm10"


def test_naver_wind_units_and_boundaries():
    assert (
        parse_weather_snapshot(naver_html(temperature="-50"), NOW).numeric[
            "temperature"
        ]
        == -50
    )
    snapshot = parse_weather_snapshot(naver_html().replace("1.5m/s", "36km/h"), NOW)
    assert snapshot.numeric["wind_speed"] == 10
    snapshot = parse_weather_snapshot(naver_html().replace("1.5m/s", "36knots"), NOW)
    assert snapshot.value_errors["wind_speed"] == "unknown_unit:wind_speed"
    snapshot = parse_weather_snapshot(naver_html().replace("50%", "101%"), NOW)
    assert snapshot.value_errors["humidity"] == "out_of_range:humidity"


def test_migration_folds_options_preserving_effective_settings():
    async def run():
        entry = SimpleNamespace(
            version=3,
            data={**TEST_CONFIG, "location_id": "old"},
            options={"kma_code": "1234567890", "location_id": "new", "other": True},
        )
        changes = {}
        hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_update_entry=lambda _, **kw: changes.update(kw)
            )
        )
        assert await async_migrate_entry(hass, entry)
        assert changes["data"]["kma_code"] == "1234567890"
        assert changes["data"]["location_id"] == "new"
        assert changes["options"] == {"other": True}
        assert changes["data"]["legacy_identity"] is True
        assert changes["version"] == 4

    asyncio.run(run())


def test_initial_guided_path_reset_and_recovery(monkeypatch):
    async def run():
        flow = WeatherFusionConfigFlow()
        flow.context = {"source": "user"}
        flow.hass = flow_hass()
        values = {**TEST_CONFIG, "location_id": "1100000000"}
        guided = SimpleNamespace(
            values=values,
            stations=("종로구",),
            location_label="서울",
            kma_location_label="서울특별시",
            kma_fallback=False,
        )
        prepare = AsyncMock(return_value=guided)
        monkeypatch.setattr(
            "custom_components.weather_fusion.config_flow.async_prepare_guided_setup",
            prepare,
        )
        monkeypatch.setattr(
            "custom_components.weather_fusion.config_flow.async_validate_sources",
            AsyncMock(return_value=ValidationReport({"kma": {"temperature"}})),
        )
        form = await flow.async_step_user()
        assert form["step_id"] == "user"
        form = await drive(flow, flow.async_step_user({"region": "서울"}))
        assert form["step_id"] == "air_station"
        form = await drive(
            flow, flow.async_step_air_station({"weatheri_air_station": "종로구"})
        )
        assert form["step_id"] == "review"
        form = await drive(flow, flow.async_step_review({"action": "reset"}))
        assert form["step_id"] == "air_station"
        assert prepare.await_args.args[2] is None
        await drive(
            flow, flow.async_step_air_station({"weatheri_air_station": "종로구"})
        )
        result = await flow.async_step_review({"action": "save", "name": "Home"})
        assert result["type"] == "create_entry" and result["title"] == "Home"

        other = WeatherFusionConfigFlow()
        other.hass = flow_hass()
        other.context = {"source": "user"}
        prepare.side_effect = GuidedSetupError("cannot_resolve_kma")
        form = await drive(other, other.async_step_user({"region": "서울"}))
        assert form["errors"]["base"] == "cannot_resolve_kma"
        assert form["data_schema"]({"location_id": "__advanced__"})
        form = await other.async_step_location({"location_id": "__back__"})
        assert form["step_id"] == "user" and other._guided is None
        form = await other.async_step_user({"region": "경기"})
        assert form["step_id"] == "location"
        assert (await other.async_step_location({"location_id": "__advanced__"}))[
            "step_id"
        ] == "advanced"

    asyncio.run(run())


def test_preparation_uses_saved_air_region_for_discovery(monkeypatch):
    async def run():
        from custom_components.weather_fusion.kma import KmaZone, ResolvedKmaLocation

        zone = KmaZone("1100000000", "서울", 37, 127, 1)
        monkeypatch.setattr(
            "custom_components.weather_fusion.onboarding.async_get_clientsession",
            lambda _: None,
        )
        monkeypatch.setattr(
            "custom_components.weather_fusion.onboarding.async_resolve_location",
            AsyncMock(return_value=ResolvedKmaLocation(zone, zone, True)),
        )
        fetch = AsyncMock(return_value="html")
        monkeypatch.setattr(
            "custom_components.weather_fusion.onboarding.async_fetch_html", fetch
        )
        hass = SimpleNamespace(
            async_add_executor_job=AsyncMock(return_value=["Station"])
        )
        result = await async_prepare_guided_setup(
            hass, "0101010000", {"weatheri_air_region_code": "09"}
        )
        assert fetch.await_args.args[1].endswith("a=09")
        assert result.values["weatheri_air_region_code"] == "09"

    asyncio.run(run())


def test_cancel_progress_drains_request(monkeypatch):
    async def run():
        entered = asyncio.Event()
        finished = asyncio.Event()

        async def prepare(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

        monkeypatch.setattr(
            "custom_components.weather_fusion.config_flow.async_prepare_guided_setup",
            prepare,
        )
        flow = WeatherFusionConfigFlow()
        flow.hass = flow_hass()
        flow.context = {"source": "user"}
        result = await flow.async_step_user({"region": "서울"})
        assert result["type"] == "progress"
        await entered.wait()
        polled = await flow.async_step_prepare()
        assert polled["type"] == "progress"
        flow.async_remove()
        await asyncio.gather(result["progress_task"], return_exceptions=True)
        assert finished.is_set() and result["progress_task"].cancelled()

    asyncio.run(run())


def test_weatheri_coalesces_refresh_across_midnight(monkeypatch):
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = []
        now = NOW.replace(hour=23, minute=59, second=59)
        monkeypatch.setattr(
            "custom_components.weather_fusion.fusion.dt_util.utcnow", lambda: now
        )
        manager = WeatherFusionManager(
            SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
        )

        async def update():
            calls.append(now.date())
            if len(calls) == 1:
                entered.set()
                await release.wait()

        monkeypatch.setattr(manager, "_async_update_weatheri", update)
        task = asyncio.create_task(manager.async_update_weatheri())
        await entered.wait()
        now += timedelta(seconds=2)
        await manager.async_update_weatheri()
        await manager.async_update_weatheri()
        release.set()
        await task
        assert len(calls) == 2 and calls[1] > calls[0]

    asyncio.run(run())


def test_shutdown_waits_for_owned_save():
    async def run():
        done = asyncio.Event()
        manager = WeatherFusionManager(
            SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
        )
        manager._weatheri_save_task = asyncio.create_task(done.wait())
        shutdown = asyncio.create_task(manager.async_shutdown())
        await asyncio.sleep(0)
        assert not shutdown.done()
        done.set()
        await shutdown
        assert manager._weatheri_save_task.done()

    asyncio.run(run())


def test_initialize_only_loads_cache(monkeypatch):
    async def run():
        manager = WeatherFusionManager(
            SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
        )
        load = AsyncMock()
        fetch = AsyncMock()
        monkeypatch.setattr(manager, "_async_load_weatheri_cache", load)
        monkeypatch.setattr(manager, "async_update_weatheri", fetch)
        await manager.async_initialize()
        load.assert_awaited_once()
        fetch.assert_not_awaited()

    asyncio.run(run())


def test_air_retry_has_independent_backoff_and_stops(monkeypatch):
    timers = []
    cancelled = []
    monkeypatch.setattr(
        "custom_components.weather_fusion.fusion.async_call_later",
        lambda hass, delay, callback: (
            timers.append((delay, callback)) or (lambda: cancelled.append(True))
        ),
    )
    manager = WeatherFusionManager(
        SimpleNamespace(), weatheri_store=SimpleNamespace(), settings=TEST_SETTINGS
    )
    manager._schedule_air_retry()
    manager._schedule_air_retry()
    assert len(timers) == 1 and timers[0][0] == timedelta(minutes=5)
    manager._unsub_air_retry = None
    manager._schedule_air_retry()
    assert timers[1][0] == timedelta(minutes=15)
    assert manager._weatheri_retry_count == 0
    manager.async_stop()
    assert cancelled and manager._unsub_air_retry is None
    manager._schedule_air_retry()
    assert len(timers) == 2


def test_review_schema_uses_frontend_translations_and_all_abort_reasons_exist():
    import json
    from pathlib import Path

    async def run():
        flow = WeatherFusionConfigFlow()
        flow.hass = flow_hass()
        flow.context = {"source": "user"}
        flow._pending = TEST_CONFIG
        flow._report = ValidationReport(
            {"kma": {"temperature"}}, {"kma": "missing_data"}
        )
        first = await flow.async_step_review()
        flow.hass.config.language = "en"
        second = await flow.async_step_review()
        assert first["description_placeholders"] == second["description_placeholders"]
        selector = next(
            value
            for key, value in second["data_schema"].schema.items()
            if str(key) == "missing_kma"
        )
        assert selector.config["translation_key"] == "capability"
        assert selector.config["read_only"] is True
        root = Path(__file__).parents[1] / "custom_components/weather_fusion"
        for name in ("strings.json", "translations/en.json", "translations/ko.json"):
            strings = json.loads((root / name).read_text(encoding="utf-8"))
            assert "options" not in strings
            assert {"unknown", "reconfigure_successful"} <= strings["config"][
                "abort"
            ].keys()
            assert "missing_kma" in strings["config"]["step"]["review"]["data"]
            assert {"humidity", "wind_speed"} <= strings["selector"]["capability"][
                "options"
            ].keys()

    asyncio.run(run())
