"""Native Home Assistant weather with dated forecasts."""

from datetime import datetime, timedelta

from homeassistant.components.weather import WeatherEntity, WeatherEntityFeature
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import CURRENT_MAX_AGE, DOMAIN, FORECAST_MAX_AGE
from .entity import WeatherFusionEntity
from .source import KOREA_TZ


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WeatherFusionWeather(hass.data[DOMAIN][entry.entry_id])])


class WeatherFusionWeather(WeatherFusionEntity, WeatherEntity):
    """A weather service that retains all existing sensor identities."""

    _attr_unique_id = f"{DOMAIN}_weather"
    _attr_translation_key = "weather"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    @property
    def available(self):
        return self.native_temperature is not None

    @property
    def native_temperature(self):
        return self.manager.metric("temperature").value

    @property
    def humidity(self):
        return self.manager.metric("humidity").value

    @property
    def native_wind_speed(self):
        return self.manager.metric("wind_speed").value

    @property
    def condition(self):
        snapshot = self.manager.source_snapshots()["naver_weather"]
        if snapshot.last_reported is None:
            return None
        if (
            not timedelta(0)
            <= dt_util.utcnow() - snapshot.last_reported
            <= CURRENT_MAX_AGE
        ):
            return None
        return snapshot.condition

    @property
    def extra_state_attributes(self):
        return {
            "source_status": self.manager.status(),
            "selected_sources": self.manager.metric("temperature").selected_sources,
        }

    async def async_forecast_daily(self):
        today = dt_util.utcnow().astimezone(KOREA_TZ).date()
        result = []
        for offset, prefix in enumerate(("today", "tomorrow")):
            high = self.manager.metric(f"{prefix}_high").value
            low = self.manager.metric(f"{prefix}_low").value
            if high is not None and low is not None:
                stamp = datetime.combine(
                    today + timedelta(days=offset), datetime.min.time(), KOREA_TZ
                )
                result.append(
                    {
                        "datetime": dt_util.as_utc(stamp).isoformat(),
                        "native_temperature": high,
                        "native_templow": low,
                    }
                )
        return result

    async def async_forecast_hourly(self):
        now = dt_util.utcnow()
        snapshot = self.manager.source_snapshots()["naver_weather"]
        if (
            snapshot.last_reported is None
            or not timedelta(0) <= now - snapshot.last_reported <= FORECAST_MAX_AGE
        ):
            return []
        return [
            {
                "datetime": dt_util.as_utc(item.time).isoformat(),
                "native_temperature": item.temperature,
                "condition": item.condition,
            }
            for item in snapshot.hourly
            if item.time > now and item.temperature is not None
        ]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self._forecast_updated))

    @callback
    def _forecast_updated(self):
        self.manager._spawn(self.async_update_listeners(None))
