"""Config flow for Weather Fusion."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback

from .configuration import (
    CONF_KMA_CODE,
    CONF_NAVER_AIR_QUERY,
    CONF_NAVER_WEATHER_QUERY,
    CONF_WEATHERI_AIR_REGION_CODE,
    CONF_WEATHERI_AIR_STATION,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_LOCATION,
    normalize_config,
)
from .const import DOMAIN

_TEXT = vol.All(str, vol.Strip, vol.Length(min=1, max=100))
_CODE = vol.All(str, vol.Strip, vol.Length(min=1, max=20))
_CODE_FIELDS = (
    CONF_KMA_CODE,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_AIR_REGION_CODE,
)


def _input_errors(values: dict[str, Any]) -> dict[str, str]:
    """Validate constraints that must remain UI-schema serializable."""
    return {
        field: "invalid_code"
        for field in _CODE_FIELDS
        if not str(values.get(field, "")).isdigit()
    }


def _config_schema(values: dict[str, Any]) -> vol.Schema:
    current = normalize_config(values)
    return vol.Schema(
        {
            vol.Required(CONF_KMA_CODE, default=current[CONF_KMA_CODE]): _CODE,
            vol.Required(
                CONF_NAVER_WEATHER_QUERY,
                default=current[CONF_NAVER_WEATHER_QUERY],
            ): _TEXT,
            vol.Required(
                CONF_NAVER_AIR_QUERY,
                default=current[CONF_NAVER_AIR_QUERY],
            ): _TEXT,
            vol.Required(
                CONF_WEATHERI_FORECAST_RID,
                default=current[CONF_WEATHERI_FORECAST_RID],
            ): _CODE,
            vol.Required(
                CONF_WEATHERI_FORECAST_GROUP,
                default=current[CONF_WEATHERI_FORECAST_GROUP],
            ): _CODE,
            vol.Required(
                CONF_WEATHERI_LOCATION,
                default=current[CONF_WEATHERI_LOCATION],
            ): _TEXT,
            vol.Required(
                CONF_WEATHERI_AIR_REGION_CODE,
                default=current[CONF_WEATHERI_AIR_REGION_CODE],
            ): _CODE,
            vol.Required(
                CONF_WEATHERI_AIR_STATION,
                default=current[CONF_WEATHERI_AIR_STATION],
            ): _TEXT,
        }
    )


class WeatherFusionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the singleton Weather Fusion helper."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WeatherFusionOptionsFlow:
        """Return the options flow handler."""
        return WeatherFusionOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create a configured Weather Fusion entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            if not (errors := _input_errors(user_input)):
                return self.async_create_entry(
                    title="Weather Fusion", data=normalize_config(user_input)
                )
        else:
            errors = {}
        return self.async_show_form(
            step_id="user",
            data_schema=_config_schema(user_input or {}),
            errors=errors,
        )


class WeatherFusionOptionsFlow(config_entries.OptionsFlow):
    """Edit source selectors and reload Weather Fusion."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Weather Fusion source options."""
        current = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            if not (errors := _input_errors(user_input)):
                return self.async_create_entry(
                    title="", data=normalize_config(user_input)
                )
        else:
            errors = {}
        return self.async_show_form(
            step_id="init",
            data_schema=_config_schema(user_input or current),
            errors=errors,
        )
