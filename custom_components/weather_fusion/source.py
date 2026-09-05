"""Normalized source snapshots consumed by the fusion engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

KOREA_TZ = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class HourlyForecast:
    """An absolute time, with source text retained for existing sensors."""

    time: datetime
    text: str
    temperature: float | None = None
    condition: str | None = None


@dataclass(frozen=True, slots=True)
class DailyForecast:
    """A forecast for a specific Korean calendar date."""

    day: date
    high: float
    low: float


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """One independently refreshed weather-source group."""

    group: str
    last_reported: datetime | None
    numeric: dict[str, float] = field(default_factory=dict)
    text: dict[str, str] = field(default_factory=dict)
    value_errors: dict[str, str] = field(default_factory=dict)
    unavailable_reason: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    daily: tuple[DailyForecast, ...] = ()
    hourly: tuple[HourlyForecast, ...] = ()
    condition: str | None = None
