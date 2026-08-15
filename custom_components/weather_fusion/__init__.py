"""Korea Weather Fusion integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .configuration import WeatherFusionSettings
from .const import DOMAIN, PLATFORMS
from .fusion import WeatherFusionManager


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Korea Weather Fusion after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Korea Weather Fusion from a config entry."""
    settings = WeatherFusionSettings.from_mapping({**entry.data, **entry.options})
    manager = WeatherFusionManager(hass, entry.entry_id, settings=settings)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await manager.async_initialize()
    manager.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Korea Weather Fusion."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        manager: WeatherFusionManager = hass.data[DOMAIN].pop(entry.entry_id)
        manager.async_stop()
    return unloaded
