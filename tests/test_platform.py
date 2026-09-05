"""Set up and unload the real HA platforms without provider requests."""

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.util import dt as dt_util
from test_configuration import TEST_CONFIG
from test_review_regressions import naver_html

from custom_components.weather_fusion.fusion import WeatherFusionManager
from custom_components.weather_fusion.naver import parse_weather_snapshot
from custom_components.weather_fusion.onboarding import ValidationReport
from custom_components.weather_fusion.source import KOREA_TZ


def test_real_platform_setup_and_unload(tmp_path, monkeypatch):
    async def run():
        hass = HomeAssistant(str(tmp_path))
        hass.config_entries = ConfigEntries(hass, {})
        loader.async_setup(hass)
        if hasattr(device_registry, "async_setup"):
            device_registry.async_setup(hass)
        await area_registry.async_load(hass)
        await device_registry.async_load(hass)
        await entity_registry.async_load(hass)
        root = Path(__file__).resolve().parents[1] / "custom_components/weather_fusion"
        integration = loader.Integration(
            hass,
            "custom_components.weather_fusion",
            root,
            json.loads((root / "manifest.json").read_text(encoding="utf-8")),
            top_level_files={path.name for path in root.iterdir()},
        )
        hass.data[loader.DATA_CUSTOM_COMPONENTS] = {"weather_fusion": integration}
        entry = ConfigEntry(
            data=TEST_CONFIG,
            options={},
            domain="weather_fusion",
            version=3,
            minor_version=1,
            title="Test",
            unique_id="weather_fusion",
            source="user",
            discovery_keys={},
            subentries_data=[],
        )
        hass.config_entries._entries[entry.entry_id] = entry

        async def initialize(manager):
            now = dt_util.utcnow().astimezone(KOREA_TZ)
            tomorrow = now + timedelta(days=1)
            manager._naver_snapshots["naver_weather"] = parse_weather_snapshot(
                naver_html(
                    day=f"{now.month}.{now.day:02}.",
                    tomorrow=f"{tomorrow.month}.{tomorrow.day:02}.",
                ),
                now,
            )

        monkeypatch.setattr(WeatherFusionManager, "async_initialize", initialize)
        monkeypatch.setattr(WeatherFusionManager, "async_start", lambda _: None)
        try:
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
            assert len(hass.states.async_all("weather")) == 1
            weather_state = hass.states.async_all("weather")[0]
            assert weather_state.state == "sunny"
            assert weather_state.attributes["temperature"] == 31.8
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_state.entity_id, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            assert response[weather_state.entity_id]["forecast"][0]["temperature"] == 32
            weather = hass.data["weather"].get_entity(weather_state.entity_id)
            received = []
            unsubscribe = weather.async_subscribe_forecast("daily", received.append)
            hass.data["weather_fusion"][entry.entry_id]._notify()
            await hass.async_block_till_done()
            assert received and received[-1][0]["temperature"] == 32
            unsubscribe()
            registered = entity_registry.async_entries_for_config_entry(
                entity_registry.async_get(hass), entry.entry_id
            )
            assert len(registered) == 50
            original_ids = {item.unique_id: item.entity_id for item in registered}
            devices = device_registry.async_entries_for_config_entry(
                device_registry.async_get(hass), entry.entry_id
            )
            assert len(devices) == 1 and devices[0].sw_version == str(
                integration.version
            )
            monkeypatch.setattr(
                "custom_components.weather_fusion.config_flow.async_validate_sources",
                AsyncMock(
                    return_value=ValidationReport(
                        {"kma": {"temperature"}}, checked_at=dt_util.utcnow()
                    )
                ),
            )
            form = await hass.config_entries.flow.async_init(
                "weather_fusion",
                context={"source": "reconfigure", "entry_id": entry.entry_id},
            )
            form = await hass.config_entries.flow.async_configure(
                form["flow_id"], {"region": "__advanced__"}
            )
            form = await hass.config_entries.flow.async_configure(
                form["flow_id"], {**TEST_CONFIG, "weatheri_air_station": "강남구"}
            )
            assert form["step_id"] == "review"
            result = await hass.config_entries.flow.async_configure(
                form["flow_id"], {"action": "save"}
            )
            assert (
                result["type"] == "abort"
                and result["reason"] == "reconfigure_successful"
            )
            await hass.async_block_till_done()
            assert entry.data["weatheri_air_station"] == "강남구"
            assert len(hass.config_entries.async_entries("weather_fusion")) == 1
            after = entity_registry.async_entries_for_config_entry(
                entity_registry.async_get(hass), entry.entry_id
            )
            assert {item.unique_id: item.entity_id for item in after} == original_ids
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert "weather_fusion" not in hass.data or not hass.data["weather_fusion"]
        finally:
            await hass.async_stop()

    asyncio.run(run())
