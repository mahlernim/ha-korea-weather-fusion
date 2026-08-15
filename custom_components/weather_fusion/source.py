"""Normalized source snapshots consumed by the fusion engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
