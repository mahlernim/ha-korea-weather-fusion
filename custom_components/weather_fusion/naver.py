"""Naver weather and air-quality page parsing."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from .source import KOREA_TZ, DailyForecast, HourlyForecast, SourceSnapshot

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
    html: str | BeautifulSoup, selectors: dict[str, str]
) -> tuple[dict[str, str], dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser") if isinstance(html, str) else html
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
    html: str | BeautifulSoup,
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
            numeric[key] = _number(values[key], key, decimal=True)
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


def condition_from_text(text: str, *, night: bool = False) -> str | None:
    """Normalize provider conditions without inventing an unknown condition."""
    if "눈" in text and "비" in text:
        return "snowy-rainy"
    for word, condition in (
        ("천둥", "lightning-rainy"),
        ("눈", "snowy"),
        ("비", "rainy"),
        ("소나기", "rainy"),
        ("안개", "fog"),
        ("흐림", "cloudy"),
        ("구름많음", "partlycloudy"),
        ("구름조금", "partlycloudy"),
    ):
        if word in text:
            return condition
    if text == "맑음":
        return "clear-night" if night else "sunny"
    return None


def _calendar_date(value: str, reference: date) -> date | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.", value)
    if not match:
        return None
    candidates = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            candidates.append(date(year, int(match[1]), int(match[2])))
        except ValueError:
            continue
    return (
        min(candidates, key=lambda day: abs((day - reference).days))
        if candidates
        else None
    )


def parse_weather_snapshot(html: str, fetched_at: datetime) -> SourceSnapshot:
    """Parse source dates and target times, never dating an old page as today."""
    soup = BeautifulSoup(html, "html.parser")
    numeric, text, errors = parse_weather(soup)
    now = fetched_at.astimezone(KOREA_TZ)
    daily = []
    source_date = None
    for node in soup.select("li.week_item"):
        stamp = node.select_one(".date")
        day = _calendar_date(stamp.get_text(strip=True), now.date()) if stamp else None
        if "today" in node.get("class", []):
            source_date = day
        high, low = node.select_one(".highest"), node.select_one(".lowest")
        if day is None or high is None or low is None:
            continue
        try:
            hi = _number(high.get_text(), "high", decimal=True)
            lo = _number(low.get_text(), "low", decimal=True)
            if not -50 <= lo <= hi <= 60:
                continue
            daily.append(DailyForecast(day, hi, lo))
        except ValueError:
            continue
    hourly = []
    # Only the first weather graph is authoritative; pages can duplicate widgets.
    graph = soup.select_one(_HOURLY_PREFIX)
    day = source_date
    last_time = None
    if graph is not None and day is not None:
        for node in graph.select(":scope > li"):
            label = node.select_one("dt.time")
            description = node.select_one("dd.weather_box i span")
            if label is None or description is None:
                continue
            label_text = label.get_text(strip=True)
            match = re.search(r"(\d{1,2})시", label_text)
            marker = node.get("data-day")
            if marker == "tomorrow":
                day = source_date + timedelta(days=1)
            elif marker in ("after_tomorrow", "day_after_tomorrow"):
                day = source_date + timedelta(days=2)
            hour = int(match[1]) if match else 0 if marker == "tomorrow" else None
            if hour is None or not 0 <= hour <= 23:
                continue
            target = datetime.combine(day, datetime.min.time(), KOREA_TZ).replace(
                hour=hour
            )
            if last_time is not None and target <= last_time:
                # Never reinterpret unordered/duplicate slots as another day.
                continue
            last_time = target
            temperature = node.select_one("dd.degree_point .num")
            try:
                temp = (
                    _number(temperature.get_text(), "temperature", decimal=True)
                    if temperature
                    else None
                )
            except ValueError:
                temp = None
            if temp is not None and not -50 <= temp <= 60:
                temp = None
            phrase = description.get_text(strip=True)
            icon = node.select_one("i.wt_icon")
            night = icon is not None and "ico_wt2" in icon.get("class", [])
            hourly.append(
                HourlyForecast(
                    target, phrase, temp, condition_from_text(phrase, night=night)
                )
            )
    current = soup.select_one("div._today .weather_graphic .weather_main i")
    condition = (
        condition_from_text(
            current.get_text(strip=True), night="ico_wt2" in current.get("class", [])
        )
        if current
        else None
    )
    if source_date is not None and source_date != now.date():
        # An HTTP 200 can still contain yesterday's page. Its dated forecasts
        # may remain useful, but its current observations must not become fresh.
        for key in ("temperature", "humidity", "wind_speed", "wind_direction", "uv"):
            numeric.pop(key, None)
            text.pop(key, None)
            errors[key] = "current_date_mismatch"
        condition = None
    return SourceSnapshot(
        group="naver_weather",
        last_reported=fetched_at,
        numeric=numeric,
        text=text,
        value_errors=errors,
        daily=tuple(daily),
        hourly=tuple(hourly),
        condition=condition,
        attributes={"source_date": source_date.isoformat() if source_date else None},
    )
