"""Constants for Weather Fusion."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "weather_fusion"
PLATFORMS = ("sensor", "binary_sensor")

CURRENT_MAX_AGE = timedelta(hours=2)
FORECAST_MAX_AGE = timedelta(hours=36)
REEVALUATE_INTERVAL = timedelta(minutes=5)
KMA_SCAN_INTERVAL = timedelta(minutes=10)
NAVER_SCAN_INTERVAL = timedelta(minutes=15)
WEATHERI_SCAN_INTERVAL = timedelta(hours=1)
WEATHERI_AIR_MAX_AGE = timedelta(hours=3)
WEATHERI_RETRY_DELAYS = (
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=30),
)
WEATHERI_MAX_RESPONSE_BYTES = 1_000_000
SOURCE_GROUPS = {
    "naver_weather": (),
    "naver_air": (),
    "weather_go_kr": (),
    "weatheri_forecast": (),
    "weatheri_air": (),
}

KMA_METRIC_KEYS = ("temperature", "humidity", "wind_speed", "pm10", "pm25")
NAVER_NUMERIC_KEYS = (
    "temperature",
    "humidity",
    "wind_speed",
    "pm10",
    "pm25",
    "today_high",
    "today_low",
    "tomorrow_high",
    "tomorrow_low",
)
METRIC_KEYS = (
    "temperature",
    "humidity",
    "wind_speed",
    "pm10",
    "pm25",
    "today_high",
    "today_low",
    "tomorrow_high",
    "tomorrow_low",
)
FORECAST_KEYS = ("forecast_3h", "forecast_6h", "forecast_9h", "forecast_12h")
NAVER_TEXT_KEYS = ("uv", "wind_direction", *FORECAST_KEYS)
WEATHERI_NUMERIC_KEYS = (
    "today_high",
    "today_low",
    "tomorrow_high",
    "tomorrow_low",
    "pm10",
    "pm25",
    "ozone",
    "nitrogen_dioxide",
    "carbon_monoxide",
    "sulfur_dioxide",
    "aqi",
)
