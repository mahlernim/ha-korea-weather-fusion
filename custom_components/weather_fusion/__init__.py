"""Korea Weather Fusion integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .configuration import (
    ADVANCED_LOCATION_ID,
    CONF_LOCATION_ID,
    CONFIG_KEYS,
    WeatherFusionSettings,
)
from .const import DOMAIN, PLATFORMS
from .fusion import WeatherFusionManager


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Korea Weather Fusion after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Preserve existing manual selectors when adding guided onboarding metadata."""
    if entry.version > 4:
        return False
    if entry.version < 4:
        data = {**entry.data, **entry.options}
        data.setdefault(CONF_LOCATION_ID, ADVANCED_LOCATION_ID)
        # Older releases used global entity/device identifiers. Keep those IDs.
        data["legacy_identity"] = True
        location_keys = (*CONFIG_KEYS, CONF_LOCATION_ID)
        options = {
            key: value
            for key, value in entry.options.items()
            if key not in location_keys
        }
        hass.config_entries.async_update_entry(
            entry, data=data, options=options, version=4
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Korea Weather Fusion from a config entry."""
    settings = WeatherFusionSettings.from_mapping({**entry.data, **entry.options})
    manager = WeatherFusionManager(hass, entry.entry_id, settings=settings)
    manager.identity = (
        DOMAIN if entry.data.get("legacy_identity", False) else entry.entry_id
    )
    manager.device_name = entry.title
    manager.software_version = str((await async_get_integration(hass, DOMAIN)).version)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    try:
        await manager.async_initialize()
        manager.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await manager.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Korea Weather Fusion."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: WeatherFusionManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_shutdown()
    return unloaded
