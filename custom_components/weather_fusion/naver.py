"""Naver weather and air-quality page parsing."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

_HOURLY_PREFIX = "div.graph_inner._hourly_weather > ul"
_FORECAST_SUFFIX = "> dl > dd.weather_box > i > span"

WEATHER_SELECTORS = {
    "temperature": "div._today > div.weather_graphic > div.temperature_text > strong",
    "today_low": "li.week_item.today span.lowest",
    "today_high": "li.week_item.today span.highest",
    "tomorrow_low": "li.week_item.today + li.week_item span.lowest",
    "tomorrow_high": "li.week_item.today + li.week_item span.highest",
    "uv": "div.report_card_wrap > ul > li:nth-child(3) > span.box > span.txt",
    "humidity": "div._today > div.temperature_info > dl > div:nth-child(2) > dd",
    "wind_direction": "div._today > div.temperature_info > dl > div:nth-child(3) > dt",
    "wind_speed": "div._today > div.temperature_info > dl > div:nth-child(3) > dd",
    "forecast_3h": f"{_HOURLY_PREFIX} > li:nth-child(3) {_FORECAST_SUFFIX}",
    "forecast_6h": f"{_HOURLY_PREFIX} > li:nth-child(6) {_FORECAST_SUFFIX}",
    "forecast_9h": f"{_HOURLY_PREFIX} > li:nth-child(9) {_FORECAST_SUFFIX}",
    "forecast_12h": f"{_HOURLY_PREFIX} > li:nth-child(12) {_FORECAST_SUFFIX}",
}

AIR_SELECTORS = {
    "pm10": "li._fine_dust .figure_box._value",
    "pm25": "li._ultrafine_dust .figure_box._value",
}


def _texts(
    html: str, selectors: dict[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    values: dict[str, str] = {}
    errors: dict[str, str] = {}
    for key, selector in selectors.items():
        node = soup.select_one(selector)
        if node is None:
            errors[key] = f"missing_selector:{key}"
            continue
        value = node.get_text(" ", strip=True)
        if not value:
            errors[key] = f"empty_value:{key}"
            continue
        values[key] = value
    if not values:
        raise ValueError("no_values")
    return values, errors


def _number(value: str, key: str, *, decimal: bool = False) -> float:
    pattern = r"[-+]?\d+(?:\.\d+)?" if decimal else r"[-+]?\d+"
    match = re.search(pattern, value)
    if match is None:
        raise ValueError(f"non_numeric:{key}:{value}")
    return float(match.group())


def parse_weather(
    html: str,
) -> tuple[dict[str, float], dict[str, str], dict[str, str]]:
    """Parse the Naver weather page using the established selectors."""
    values, errors = _texts(html, WEATHER_SELECTORS)
    numeric: dict[str, float] = {}
    for key in (
        "temperature",
        "humidity",
        "wind_speed",
        "today_high",
        "today_low",
        "tomorrow_high",
        "tomorrow_low",
    ):
        if key not in values:
            continue
        try:
            numeric[key] = _number(values[key], key, decimal=key == "wind_speed")
        except ValueError as err:
            errors[key] = str(err)
    text = {
        key: values[key]
        for key in (
            "uv",
            "wind_direction",
            "forecast_3h",
            "forecast_6h",
            "forecast_9h",
            "forecast_12h",
        )
        if key in values
    }
    return numeric, text, errors


def parse_air(html: str) -> tuple[dict[str, float], dict[str, str]]:
    """Parse the Naver PM10 and PM2.5 page."""
    values, errors = _texts(html, AIR_SELECTORS)
    numeric: dict[str, float] = {}
    for key, value in values.items():
        try:
            numeric[key] = _number(value, key)
        except ValueError as err:
            errors[key] = str(err)
    return numeric, errors
