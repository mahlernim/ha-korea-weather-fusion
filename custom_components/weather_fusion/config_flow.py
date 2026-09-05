"""Config flow for Korea Weather Fusion."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

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
    CONFIG_KEYS,
    normalize_config,
)
from .const import DOMAIN
from .onboarding import (
    GuidedSetupError,
    async_finalize_guided_values,
    async_prepare_guided_setup,
    async_validate_sources,
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
    patterns = {
        CONF_KMA_CODE: r"[0-9]{10}",
        CONF_WEATHERI_FORECAST_RID: r"[0-9]{10}",
        CONF_WEATHERI_FORECAST_GROUP: r"[0-9]{1,2}",
        CONF_WEATHERI_AIR_REGION_CODE: r"[0-9]{1,2}",
    }
    return {
        key: "invalid_code"
        for key, pattern in patterns.items()
        if not re.fullmatch(pattern, str(values.get(key, ""))) or int(values[key]) == 0
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


def _location_schema(
    default: str | None = None, region: str | None = None
) -> vol.Schema:
    options = [
        (rid, label)
        for rid, label in location_options()
        if region is None or label.split(" · ")[0] == region
    ]
    if region is None:
        options.append((ADVANCED_LOCATION_ID, "고급 수동 설정 / Advanced manual setup"))
    if default not in dict(options):
        default = None
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


class _SetupFlow:
    """Shared guided/manual review steps for setup, options and reconfiguration."""

    def __init__(self):
        super().__init__()
        self._guided = None
        self._selected_station = None
        self._selected_location = None
        self._region = None
        self._pending = {}
        self._report = None
        self._start_step = "user"

    def _current(self):
        return {}

    async def _start(self, step_id, user_input):
        self._start_step = step_id
        current = self._pending or self._current()
        if user_input is not None:
            if CONF_LOCATION_ID in user_input:
                return await self.async_step_location(user_input)
            self._region = user_input["region"]
            if self._region == ADVANCED_LOCATION_ID:
                return await self.async_step_advanced()
            return await self.async_step_location()
        default_location = current.get(CONF_LOCATION_ID)
        regions = sorted({label.split(" · ")[0] for _, label in location_options()})
        default = next(
            (
                label.split(" · ")[0]
                for rid, label in location_options()
                if rid == default_location
            ),
            None,
        )
        choices = [(region, region) for region in regions] + [
            (ADVANCED_LOCATION_ID, "고급 수동 설정 / Advanced manual setup")
        ]
        key = (
            vol.Required("region", default=default)
            if default
            else vol.Required("region")
        )
        return self.async_show_form(
            step_id=step_id, data_schema=vol.Schema({key: _selector(choices)})
        )

    async def async_step_location(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._selected_location = str(user_input[CONF_LOCATION_ID])
            if self._selected_location == ADVANCED_LOCATION_ID:
                return await self.async_step_advanced()
            try:
                self._guided = await async_prepare_guided_setup(
                    self.hass, self._selected_location
                )
            except GuidedSetupError as err:
                errors["base"] = err.translation_key
            else:
                current = self._current()
                if current.get(CONF_LOCATION_ID) == self._selected_location:
                    self._selected_station = current.get(CONF_WEATHERI_AIR_STATION)
                else:
                    self._selected_station = None
                self._report = None
                return await self.async_step_air_station()
        default = self._selected_location or self._current().get(CONF_LOCATION_ID)
        return self.async_show_form(
            step_id="location",
            data_schema=_location_schema(default, self._region),
            errors=errors,
        )

    async def async_step_air_station(self, user_input=None):
        if self._guided is None:
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            self._selected_station = str(user_input[CONF_WEATHERI_AIR_STATION])
            if self._selected_station not in self._guided.stations:
                errors[CONF_WEATHERI_AIR_STATION] = "invalid_station"
            else:
                values = await async_finalize_guided_values(
                    self.hass, self._guided, self._selected_station
                )
                current = self._current()
                if current.get(CONF_LOCATION_ID) == values[CONF_LOCATION_ID]:
                    # Retain existing fine-grained overrides within this location.
                    values = {
                        **values,
                        **current,
                        CONF_WEATHERI_AIR_STATION: self._selected_station,
                    }
                self._pending = values
                self._report = await async_validate_sources(self.hass, values)
                return await self.async_step_review()
        return self.async_show_form(
            step_id="air_station",
            data_schema=_station_schema(self._guided.stations, self._selected_station),
            errors=errors,
            description_placeholders={
                "location": self._guided.location_label,
                "kma_location": self._guided.kma_location_label,
            },
        )

    async def async_step_advanced(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = _input_errors(user_input)
            if not errors:
                self._guided = None
                self._pending = _advanced_values(user_input)
                self._report = await async_validate_sources(self.hass, self._pending)
                return await self.async_step_review()
        return self.async_show_form(
            step_id="advanced",
            data_schema=_config_schema(user_input or self._pending or self._current()),
            errors=errors,
        )

    async def async_step_review(self, user_input=None):
        if self._report is None:
            return self.async_abort(reason="unknown")
        errors = {}
        if user_input is not None:
            action = user_input["action"]
            if action == "edit":
                if self._guided is None:
                    return await self.async_step_advanced()
                return await self._start(self._start_step, None)
            if action == "retry":
                self._report = await async_validate_sources(
                    self.hass, self._pending, self._report
                )
            elif action == "save":
                # Do not silently accept checks that aged while the form was open.
                if (
                    self._report.checked_at
                    and dt_util.utcnow() - self._report.checked_at
                    >= timedelta(minutes=5)
                ):
                    self._report = await async_validate_sources(
                        self.hass, self._pending
                    )
                    errors["base"] = "checks_refreshed"
                elif self._report.usable and (
                    self._report.complete or user_input.get("allow_limited", False)
                ):
                    return self._finish()
                else:
                    errors["base"] = (
                        "limited_confirmation"
                        if self._report.usable
                        else "no_usable_sources"
                    )
        fields = {
            vol.Required(
                "action", default="save" if self._report.complete else "retry"
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["save", "retry", "edit"],
                    translation_key="review_action",
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
        if not self._report.complete:
            fields[vol.Optional("allow_limited", default=False)] = bool
        ko = getattr(getattr(self.hass, "config", None), "language", "en") == "ko"
        labels = {
            "ready": "정상" if ko else "Ready",
            "missing_data": "일부 데이터 없음" if ko else "Some data missing",
            "stale_data": "오래된 데이터" if ko else "Stale data",
            "cannot_validate": "연결 또는 데이터 확인 실패"
            if ko
            else "Connection or data check failed",
        }
        summary = {}
        capability_names = {
            "temperature": "기온" if ko else "temperature",
            "humidity": "습도" if ko else "humidity",
            "wind_speed": "풍속" if ko else "wind speed",
            "daily": "오늘·내일 예보" if ko else "today/tomorrow forecast",
            "pm10": "PM10",
            "pm25": "PM2.5",
            **{
                f"forecast_{hours}h": f"{hours}시간 후 예보"
                if ko
                else f"{hours}h forecast"
                for hours in (3, 6, 9, 12)
            },
        }
        for key in (
            "kma",
            "naver_weather",
            "naver_air",
            "weatheri_forecast",
            "weatheri_air",
        ):
            summary[key] = labels[self._report.errors.get(key, "ready")]
            if missing := self._report.missing.get(key):
                summary[key] += (
                    " (" + ", ".join(capability_names[item] for item in missing) + ")"
                )
        return self.async_show_form(
            step_id="review",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                **summary,
                "location": self._guided.location_label
                if self._guided
                else self._pending.get(CONF_WEATHERI_LOCATION, ""),
                "kma_location": self._guided.kma_location_label
                if self._guided
                and self._pending[CONF_KMA_CODE] == self._guided.values[CONF_KMA_CODE]
                else self._pending[CONF_KMA_CODE],
                "naver_query": self._pending[CONF_NAVER_WEATHER_QUERY],
                "weatheri_location": self._pending[CONF_WEATHERI_LOCATION],
                "station": self._pending[CONF_WEATHERI_AIR_STATION],
            },
        )


class WeatherFusionConfigFlow(_SetupFlow, config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one service while preserving its stable identity."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return WeatherFusionOptionsFlow()

    def _current(self):
        if self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            return {**entry.data, **entry.options}
        return {}

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self._start("user", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._start("reconfigure", user_input)

    def _finish(self):
        if self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            options = {
                key: value
                for key, value in entry.options.items()
                if key not in (*CONFIG_KEYS, CONF_LOCATION_ID)
            }
            # The existing entry listener owns reloads, including reconfiguration.
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, **self._pending}, options=options
            )
            return self.async_abort(reason="reconfigure_successful")
        return self.async_create_entry(title="Korea Weather Fusion", data=self._pending)


class WeatherFusionOptionsFlow(_SetupFlow, config_entries.OptionsFlow):
    """Keep the existing Configure entry point compatible with reconfiguration."""

    def _current(self):
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input=None):
        return await self._start("init", user_input)

    def _finish(self):
        return self.async_create_entry(
            title="", data={**self.config_entry.options, **self._pending}
        )
