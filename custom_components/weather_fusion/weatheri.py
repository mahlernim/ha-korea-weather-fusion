"""Bounded Weatheri fetching, parsing, and persistent data models."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

import aiohttp
from bs4 import BeautifulSoup, Tag

from .const import WEATHERI_MAX_RESPONSE_BYTES

_DATE_PATTERN = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_TEMP_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)\s*[˚°]\s*C", re.IGNORECASE)
_SHOWTHREE_PATTERN = re.compile(r'^showthree\(["\'](\d+)["\']\)$')
_SOURCE_TIME_PATTERN = re.compile(
    r"한국환경공단\s*,\s*(\d{2})\.(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})"
)
_AIR_HEADERS = {
    "pm10": ("PM10", "미세먼지"),
    "pm25": ("PM2.5", "초미세먼지"),
    "ozone": ("오존",),
    "nitrogen_dioxide": ("이산화질소",),
    "carbon_monoxide": ("일산화탄소",),
    "sulfur_dioxide": ("아황산가스",),
    "aqi": ("대기통합지수", "통합대기지수"),
}
_AIR_LIMITS = {
    "pm10": (0, 2000),
    "pm25": (0, 2000),
    "ozone": (0, 5),
    "nitrogen_dioxide": (0, 5),
    "carbon_monoxide": (0, 100),
    "sulfur_dioxide": (0, 5),
    "aqi": (0, 1000),
}
AIR_KEYS = tuple(_AIR_HEADERS)
_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
    "User-Agent": "Home Assistant Weather Fusion",
}


class WeatheriError(Exception):
    """Raised when a Weatheri resource cannot be used safely."""


@dataclass(frozen=True, slots=True)
class WeatheriForecast:
    """Validated same-day Weatheri forecast."""

    location: str
    source_date: date
    fetched_at: datetime
    today_high: float
    today_low: float
    tomorrow_high: float
    tomorrow_low: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "source_date": self.source_date.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "today_high": self.today_high,
            "today_low": self.today_low,
            "tomorrow_high": self.tomorrow_high,
            "tomorrow_low": self.tomorrow_low,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WeatheriForecast:
        return cls(
            location=str(value["location"]),
            source_date=date.fromisoformat(value["source_date"]),
            fetched_at=datetime.fromisoformat(value["fetched_at"]),
            today_high=float(value["today_high"]),
            today_low=float(value["today_low"]),
            tomorrow_high=float(value["tomorrow_high"]),
            tomorrow_low=float(value["tomorrow_low"]),
        )


@dataclass(frozen=True, slots=True)
class WeatheriAir:
    """Validated Weatheri air-quality observation."""

    station: str
    source_updated_at: datetime
    fetched_at: datetime
    measurements: dict[str, float | None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "station": self.station,
            "source_updated_at": self.source_updated_at.isoformat(),
            "fetched_at": self.fetched_at.isoformat(),
            "measurements": self.measurements,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WeatheriAir:
        raw = value["measurements"]
        return cls(
            station=str(value["station"]),
            source_updated_at=datetime.fromisoformat(value["source_updated_at"]),
            fetched_at=datetime.fromisoformat(value["fetched_at"]),
            measurements={
                key: None if raw.get(key) is None else float(raw[key])
                for key in AIR_KEYS
            },
        )


async def async_fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    """Fetch a bounded UTF-8 Weatheri page."""
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with asyncio.timeout(16):
            async with session.get(
                url, timeout=timeout, headers=_REQUEST_HEADERS
            ) as response:
                if response.status != 200:
                    raise WeatheriError(f"Weatheri returned HTTP {response.status}")
                if (
                    response.content_length is not None
                    and response.content_length > WEATHERI_MAX_RESPONSE_BYTES
                ):
                    raise WeatheriError("Weatheri response is too large")
                chunks: list[bytes] = []
                received = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    received += len(chunk)
                    if received > WEATHERI_MAX_RESPONSE_BYTES:
                        raise WeatheriError("Weatheri response is too large")
                    chunks.append(chunk)
    except WeatheriError:
        raise
    except (TimeoutError, aiohttp.ClientError) as err:
        raise WeatheriError(f"Unable to fetch Weatheri: {err}") from err
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as err:
        raise WeatheriError("Weatheri response is not valid UTF-8") from err


def parse_forecast(
    html: str, *, location: str, current_date: date, fetched_at: datetime
) -> WeatheriForecast:
    """Parse and validate today's and tomorrow's summary temperatures."""
    soup = BeautifulSoup(html, "html.parser")
    cells: dict[int, Tag] = {}
    for cell in soup.find_all("td", onclick=True):
        match = _SHOWTHREE_PATTERN.fullmatch(str(cell.get("onclick", "")).strip())
        if match:
            cells[int(match.group(1))] = cell
    today_cell, tomorrow_cell = cells.get(1), cells.get(2)
    if today_cell is None or tomorrow_cell is None:
        raise WeatheriError("Today or tomorrow summary cell is missing")
    table = today_cell.find_parent("table")
    if table is None or tomorrow_cell not in table.descendants:
        raise WeatheriError("Today and tomorrow are not in one summary table")
    parsed_dates = _summary_dates(table, current_date)
    tomorrow = current_date + timedelta(days=1)
    if len(parsed_dates) < 2 or parsed_dates[:2] != [current_date, tomorrow]:
        raise WeatheriError("Forecast dates do not match today and tomorrow")
    today_high, today_low = _summary_temperatures(today_cell)
    tomorrow_high, tomorrow_low = _summary_temperatures(tomorrow_cell)
    return WeatheriForecast(
        location,
        current_date,
        fetched_at,
        today_high,
        today_low,
        tomorrow_high,
        tomorrow_low,
    )


def parse_air(
    html: str, *, station: str, fetched_at: datetime, local_tz: tzinfo
) -> WeatheriAir:
    """Parse one monitoring-station observation using semantic headers."""
    soup = BeautifulSoup(html, "html.parser")
    source_updated_at = _source_timestamp(soup, local_tz)
    if source_updated_at - fetched_at > timedelta(minutes=5):
        raise WeatheriError("Air-quality source timestamp is in the future")
    table, header_row, columns = _find_air_table(soup)
    rows = table.find_all("tr")
    target: list[str] | None = None
    for row in rows[rows.index(header_row) + 1 :]:
        cells = _row_cells(row)
        if cells and cells[0] == station:
            target = cells
            break
    if target is None:
        raise WeatheriError(f"Air-quality station was not found: {station}")
    measurements: dict[str, float | None] = {}
    for key in AIR_KEYS:
        raw = target[columns[key]] if columns[key] < len(target) else "-"
        measurements[key] = _parse_air_value(key, raw)
    return WeatheriAir(station, source_updated_at, fetched_at, measurements)


def _summary_dates(table: Tag, reference: date) -> list[date]:
    dates: list[date] = []
    for month_text, day_text in _DATE_PATTERN.findall(table.get_text(" ", strip=True)):
        month, day = int(month_text), int(day_text)
        candidates = []
        for year in (reference.year - 1, reference.year, reference.year + 1):
            try:
                candidates.append(date(year, month, day))
            except ValueError as err:
                raise WeatheriError(f"Invalid forecast date {month}/{day}") from err
        parsed = min(candidates, key=lambda item: abs((item - reference).days))
        if not dates or dates[-1] != parsed:
            dates.append(parsed)
    return dates


def _summary_temperatures(cell: Tag) -> tuple[float, float]:
    values = [
        float(value) for value in _TEMP_PATTERN.findall(cell.get_text(" ", strip=True))
    ]
    if len(values) < 2:
        raise WeatheriError("High or low temperature is missing")
    high, low = values[:2]
    if any(value < -50 or value > 60 for value in (high, low)):
        raise WeatheriError("Temperature is outside the valid range")
    if high < low:
        raise WeatheriError("High temperature is lower than low temperature")
    return high, low


def _find_air_table(soup: BeautifulSoup) -> tuple[Tag, Tag, dict[str, int]]:
    for row in soup.find_all("tr"):
        cells = _row_cells(row)
        if len(cells) < 8 or not any("PM10" in cell for cell in cells):
            continue
        if not any("PM2.5" in cell for cell in cells):
            continue
        columns: dict[str, int] = {}
        for key, aliases in _AIR_HEADERS.items():
            for alias in aliases:
                matches = [index for index, cell in enumerate(cells) if alias in cell]
                if matches:
                    columns[key] = matches[0]
                    break
        if set(columns) == set(AIR_KEYS) and len(set(columns.values())) == len(
            AIR_KEYS
        ):
            table = row.find_parent("table")
            if table is not None:
                return table, row, columns
    raise WeatheriError("Air-quality observation table is missing")


def _source_timestamp(soup: BeautifulSoup, local_tz: tzinfo) -> datetime:
    match = _SOURCE_TIME_PATTERN.search(soup.get_text(" ", strip=True))
    if not match:
        raise WeatheriError("Air-quality source timestamp is missing")
    year, month, day, hour, minute = (int(part) for part in match.groups())
    try:
        return datetime(2000 + year, month, day, hour, minute, tzinfo=local_tz)
    except ValueError as err:
        raise WeatheriError("Air-quality source timestamp is invalid") from err


def _parse_air_value(key: str, raw: str) -> float | None:
    value = raw.strip()
    if value in {"", "-"}:
        return None
    try:
        parsed = float(value.replace(",", ""))
    except ValueError as err:
        raise WeatheriError(f"Invalid {key} value: {value}") from err
    lower, upper = _AIR_LIMITS[key]
    if not lower <= parsed <= upper:
        raise WeatheriError(f"{key} value is outside the valid range: {parsed}")
    return parsed


def _row_cells(row: Tag) -> list[str]:
    values = [
        cell.get_text(" ", strip=True)
        for cell in row.find_all(["th", "td"], recursive=False)
    ]
    return [value for value in values if value]
