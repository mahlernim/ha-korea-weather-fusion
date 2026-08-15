"""Configuration model and source URL builders for Korea Weather Fusion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

CONF_KMA_CODE = "kma_code"
CONF_NAVER_WEATHER_QUERY = "naver_weather_query"
CONF_NAVER_AIR_QUERY = "naver_air_query"
CONF_WEATHERI_FORECAST_RID = "weatheri_forecast_rid"
CONF_WEATHERI_FORECAST_GROUP = "weatheri_forecast_group"
CONF_WEATHERI_LOCATION = "weatheri_location"
CONF_WEATHERI_AIR_REGION_CODE = "weatheri_air_region_code"
CONF_WEATHERI_AIR_STATION = "weatheri_air_station"

CONFIG_KEYS = (
    CONF_KMA_CODE,
    CONF_NAVER_WEATHER_QUERY,
    CONF_NAVER_AIR_QUERY,
    CONF_WEATHERI_FORECAST_RID,
    CONF_WEATHERI_FORECAST_GROUP,
    CONF_WEATHERI_LOCATION,
    CONF_WEATHERI_AIR_REGION_CODE,
    CONF_WEATHERI_AIR_STATION,
)


def normalize_config(values: Mapping[str, Any]) -> dict[str, str]:
    """Return a complete, whitespace-normalized configuration."""
    return {key: str(values.get(key, "")).strip() for key in CONFIG_KEYS}


@dataclass(frozen=True, slots=True)
class WeatherFusionSettings:
    """Resolved source selectors for one Korea Weather Fusion entry."""

    kma_code: str
    naver_weather_query: str
    naver_air_query: str
    weatheri_forecast_rid: str
    weatheri_forecast_group: str
    weatheri_location: str
    weatheri_air_region_code: str
    weatheri_air_station: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> WeatherFusionSettings:
        """Build settings from complete config-entry data/options."""
        config = normalize_config(values)
        return cls(**config)

    @property
    def kma_url(self) -> str:
        return (
            "https://www.weather.go.kr/w/wnuri-fct2021/main/current-weather.do?"
            + urlencode({"code": self.kma_code})
        )

    @property
    def naver_weather_url(self) -> str:
        return "https://m.search.naver.com/search.naver?" + urlencode(
            {
                "where": "m",
                "sm": "top_hty",
                "fbm": "1",
                "ie": "utf8",
                "query": self.naver_weather_query,
            }
        )

    @property
    def naver_air_url(self) -> str:
        return "https://m.search.naver.com/search.naver?" + urlencode(
            {
                "where": "m",
                "sm": "mtb_etc",
                "pkid": "227",
                "qvt": "0",
                "query": self.naver_air_query,
            }
        )

    @property
    def weatheri_forecast_url(self) -> str:
        return "https://www.weatheri.co.kr/forecast/forecast01.php?" + urlencode(
            {
                "rid": self.weatheri_forecast_rid,
                "k": self.weatheri_forecast_group,
                "a_name": self.weatheri_location,
            }
        )

    @property
    def weatheri_air_url(self) -> str:
        return "https://www.weatheri.co.kr/special/special05_1.php?" + urlencode(
            {"a": self.weatheri_air_region_code}
        )
