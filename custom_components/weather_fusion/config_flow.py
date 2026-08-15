"""Config flow for Korea Weather Fusion."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .catalog import location_options
from .configuration import (
    ADVANCED_LOCATION_ID,
    CONF_KMA_CODE,
    CONF_LOCATION_ID,
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
from .onboarding import (
    GuidedSetup,
    GuidedSetupError,
    async_finalize_guided_values,
    async_prepare_guided_setup,
    async_validate_guided_setup,
)

_TEXT = vol.All(str, vol.Strip, vol.Length(min=1, max=100))
_CODE = vol.All(str, vol.Strip, vol.Length(min=1, max=20))
_CODE_FIELDS = (
    CONF_KMA_CODE,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_AIR_REGION_CODE,
)


def _selector(options: list[tuple[str, str]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[{"value": value, "label": label} for value, label in options],
            mode=SelectSelectorMode.DROPDOWN,
            sort=False,
        )
    )


def _input_errors(values: dict[str, Any]) -> dict[str, str]:
    """Validate constraints that must remain UI-schema serializable."""
    return {
        field: "invalid_code"
        for field in _CODE_FIELDS
        if not str(values.get(field, "")).isdigit()
    }


def _config_schema(values: dict[str, Any]) -> vol.Schema:
    """Return the advanced source-selector form."""
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


def _location_schema(default: str | None = None) -> vol.Schema:
    options = location_options()
    options.append((ADVANCED_LOCATION_ID, "고급 수동 설정 / Advanced manual setup"))
    key = (
        vol.Required(CONF_LOCATION_ID, default=default)
        if default
        else vol.Required(CONF_LOCATION_ID)
    )
    return vol.Schema({key: _selector(options)})


def _station_schema(
    stations: tuple[str, ...], default: str | None = None
) -> vol.Schema:
    selected = default if default in stations else stations[0]
    return vol.Schema(
        {
            vol.Required(CONF_WEATHERI_AIR_STATION, default=selected): _selector(
                [(station, station) for station in stations]
            )
        }
    )


def _advanced_values(values: dict[str, Any]) -> dict[str, str]:
    return {CONF_LOCATION_ID: ADVANCED_LOCATION_ID, **normalize_config(values)}


class WeatherFusionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the singleton Korea Weather Fusion helper."""

    VERSION = 3

    def __init__(self) -> None:
        self._guided: GuidedSetup | None = None
        self._selected_station: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> WeatherFusionOptionsFlow:
        """Return the options flow handler."""
        return WeatherFusionOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a guided catalog location or advanced setup."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            location_id = str(user_input[CONF_LOCATION_ID])
            if location_id == ADVANCED_LOCATION_ID:
                return await self.async_step_advanced()
            try:
                self._guided = await async_prepare_guided_setup(self.hass, location_id)
            except GuidedSetupError as err:
                errors["base"] = err.translation_key
            else:
                return await self.async_step_air_station()
        return self.async_show_form(
            step_id="user",
            data_schema=_location_schema(),
            errors=errors,
        )

    async def async_step_air_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose and validate a Weatheri air station."""
        if self._guided is None:
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            station = str(user_input[CONF_WEATHERI_AIR_STATION])
            self._selected_station = station
            if station not in self._guided.stations:
                errors[CONF_WEATHERI_AIR_STATION] = "invalid_station"
            else:
                try:
                    values = await async_finalize_guided_values(
                        self.hass, self._guided, station
                    )
                except GuidedSetupError as err:
                    errors["base"] = err.translation_key
                else:
                    validation_errors = await async_validate_guided_setup(
                        self.hass,
                        values,
                        weatheri_air_html=self._guided.weatheri_air_html,
                    )
                    if validation_errors:
                        errors["base"] = next(iter(validation_errors.values()))
                    else:
                        return self.async_create_entry(
                            title="Korea Weather Fusion", data=values
                        )
        return self.async_show_form(
            step_id="air_station",
            data_schema=_station_schema(self._guided.stations, self._selected_station),
            errors=errors,
            description_placeholders={
                "location": self._guided.location_label,
                "kma_location": self._guided.kma_location_label,
            },
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure every source selector manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _input_errors(user_input)):
                return self.async_create_entry(
                    title="Korea Weather Fusion",
                    data=_advanced_values(user_input),
                )
        return self.async_show_form(
            step_id="advanced",
            data_schema=_config_schema(user_input or {}),
            errors=errors,
        )


class WeatherFusionOptionsFlow(config_entries.OptionsFlow):
    """Edit a guided location or advanced source selectors."""

    def __init__(self) -> None:
        self._guided: GuidedSetup | None = None
        self._selected_station: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a guided catalog location or advanced settings."""
        current = {**self.config_entry.data, **self.config_entry.options}
        default = str(current.get(CONF_LOCATION_ID, ADVANCED_LOCATION_ID))
        errors: dict[str, str] = {}
        if user_input is not None:
            location_id = str(user_input[CONF_LOCATION_ID])
            if location_id == ADVANCED_LOCATION_ID:
                return await self.async_step_advanced()
            try:
                self._guided = await async_prepare_guided_setup(self.hass, location_id)
            except GuidedSetupError as err:
                errors["base"] = err.translation_key
            else:
                return await self.async_step_air_station()
        return self.async_show_form(
            step_id="init",
            data_schema=_location_schema(default),
            errors=errors,
        )

    async def async_step_air_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose and validate a Weatheri air station."""
        if self._guided is None:
            return self.async_abort(reason="unknown")
        errors: dict[str, str] = {}
        if user_input is not None:
            station = str(user_input[CONF_WEATHERI_AIR_STATION])
            self._selected_station = station
            if station not in self._guided.stations:
                errors[CONF_WEATHERI_AIR_STATION] = "invalid_station"
            else:
                try:
                    values = await async_finalize_guided_values(
                        self.hass, self._guided, station
                    )
                except GuidedSetupError as err:
                    errors["base"] = err.translation_key
                else:
                    validation_errors = await async_validate_guided_setup(
                        self.hass,
                        values,
                        weatheri_air_html=self._guided.weatheri_air_html,
                    )
                    if validation_errors:
                        errors["base"] = next(iter(validation_errors.values()))
                    else:
                        return self.async_create_entry(title="", data=values)
        return self.async_show_form(
            step_id="air_station",
            data_schema=_station_schema(self._guided.stations, self._selected_station),
            errors=errors,
            description_placeholders={
                "location": self._guided.location_label,
                "kma_location": self._guided.kma_location_label,
            },
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit every source selector manually."""
        current = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _input_errors(user_input)):
                return self.async_create_entry(
                    title="", data=_advanced_values(user_input)
                )
        return self.async_show_form(
            step_id="advanced",
            data_schema=_config_schema(user_input or current),
            errors=errors,
        )
