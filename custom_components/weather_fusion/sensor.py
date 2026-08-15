"""Representative Weather Fusion sensors."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WeatherFusionEntity
from .fusion import WeatherFusionManager

NUMERIC_SENSORS = (
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="wind_speed",
        translation_key="wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="today_high",
        translation_key="today_high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="today_low",
        translation_key="today_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="tomorrow_high",
        translation_key="tomorrow_high",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="tomorrow_low",
        translation_key="tomorrow_low",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)

KMA_SENSORS = (
    SensorEntityDescription(
        key="kma_temperature",
        translation_key="kma_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="kma_humidity",
        translation_key="kma_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="kma_wind_speed",
        translation_key="kma_wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="kma_pm10",
        translation_key="kma_pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="kma_pm25",
        translation_key="kma_pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)

FORECAST_SENSORS = tuple(
    SensorEntityDescription(
        key=f"forecast_{hours}h", translation_key=f"forecast_{hours}h"
    )
    for hours in (3, 6, 9, 12)
)

NAVER_NUMERIC_SENSORS = (
    SensorEntityDescription(
        key="naver_temperature",
        translation_key="naver_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="naver_humidity",
        translation_key="naver_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="naver_wind_speed",
        translation_key="naver_wind_speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="naver_pm10",
        translation_key="naver_pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="naver_pm25",
        translation_key="naver_pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        SensorEntityDescription(
            key=f"naver_{key}",
            translation_key=f"naver_{key}",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low")
    ),
)

NAVER_TEXT_SENSORS = tuple(
    SensorEntityDescription(key=f"naver_{key}", translation_key=f"naver_{key}")
    for key in (
        "uv",
        "wind_direction",
        "forecast_3h",
        "forecast_6h",
        "forecast_9h",
        "forecast_12h",
    )
)

WEATHERI_NUMERIC_SENSORS = (
    *(
        SensorEntityDescription(
            key=f"weatheri_{key}",
            translation_key=f"weatheri_{key}",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for key in ("today_high", "today_low", "tomorrow_high", "tomorrow_low")
    ),
    SensorEntityDescription(
        key="weatheri_pm10",
        translation_key="weatheri_pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="weatheri_pm25",
        translation_key="weatheri_pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        SensorEntityDescription(
            key=f"weatheri_{key}",
            translation_key=f"weatheri_{key}",
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        )
        for key, unit in (
            ("ozone", "ppm"),
            ("nitrogen_dioxide", "ppm"),
            ("carbon_monoxide", "ppm"),
            ("sulfur_dioxide", "ppm"),
            ("aqi", "AQI"),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up representative sensors."""
    manager: WeatherFusionManager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [WeatherFusionSensor(manager, item) for item in NUMERIC_SENSORS]
        + [WeatherFusionKmaSensor(manager, item) for item in KMA_SENSORS]
        + [WeatherFusionForecastSensor(manager, item) for item in FORECAST_SENSORS]
        + [
            WeatherFusionNaverNumericSensor(manager, item)
            for item in NAVER_NUMERIC_SENSORS
        ]
        + [WeatherFusionNaverTextSensor(manager, item) for item in NAVER_TEXT_SENSORS]
        + [
            WeatherFusionWeatheriNumericSensor(manager, item)
            for item in WEATHERI_NUMERIC_SENSORS
        ]
    )


class WeatherFusionSensor(WeatherFusionEntity, SensorEntity):
    """One fused representative numeric metric."""

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.manager.metric(self.entity_description.key).value is not None

    @property
    def native_value(self) -> float | None:
        return self.manager.metric(self.entity_description.key).value

    @property
    def extra_state_attributes(self):
        return self.manager.metric(self.entity_description.key).attributes


class WeatherFusionForecastSensor(WeatherFusionEntity, SensorEntity):
    """One fresh text forecast."""

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.manager.forecast(self.entity_description.key).value is not None

    @property
    def native_value(self) -> str | None:
        return self.manager.forecast(self.entity_description.key).value

    @property
    def extra_state_attributes(self):
        return self.manager.forecast(self.entity_description.key).attributes


class WeatherFusionKmaSensor(WeatherFusionEntity, SensorEntity):
    """One raw direct weather.go.kr metric."""

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._kma_key = description.key.removeprefix("kma_")
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.manager.kma_metric(self._kma_key).value is not None

    @property
    def native_value(self) -> float | None:
        return self.manager.kma_metric(self._kma_key).value

    @property
    def extra_state_attributes(self):
        return self.manager.kma_metric_attributes(self._kma_key)


class WeatherFusionNaverNumericSensor(WeatherFusionEntity, SensorEntity):
    """One raw direct Naver numeric metric."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._naver_key = description.key.removeprefix("naver_")
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.manager.naver_numeric_metric(self._naver_key).value is not None

    @property
    def native_value(self) -> float | None:
        return self.manager.naver_numeric_metric(self._naver_key).value

    @property
    def extra_state_attributes(self):
        return self.manager.naver_metric_attributes(self._naver_key)


class WeatherFusionNaverTextSensor(WeatherFusionEntity, SensorEntity):
    """One raw direct Naver text metric."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._naver_key = description.key.removeprefix("naver_")
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return self.manager.naver_text_metric(self._naver_key).value is not None

    @property
    def native_value(self) -> str | None:
        return self.manager.naver_text_metric(self._naver_key).value

    @property
    def extra_state_attributes(self):
        return self.manager.naver_metric_attributes(self._naver_key)


class WeatherFusionWeatheriNumericSensor(WeatherFusionEntity, SensorEntity):
    """One raw direct Weatheri numeric metric."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, manager: WeatherFusionManager, description: SensorEntityDescription
    ) -> None:
        super().__init__(manager)
        self.entity_description = description
        self._weatheri_key = description.key.removeprefix("weatheri_")
        self._attr_unique_id = f"{DOMAIN}_{description.key}"

    @property
    def suggested_object_id(self) -> str:
        return self.entity_description.key

    @property
    def available(self) -> bool:
        return (
            self.manager.weatheri_numeric_metric(self._weatheri_key).value is not None
        )

    @property
    def native_value(self) -> float | None:
        return self.manager.weatheri_numeric_metric(self._weatheri_key).value

    @property
    def extra_state_attributes(self):
        return self.manager.weatheri_metric_attributes(self._weatheri_key)
