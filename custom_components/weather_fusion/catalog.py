"""Packaged Korean location catalog for guided onboarding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ForecastLocation:
    """One supported Weatheri forecast location."""

    rid: str
    name: str
    label: str
    forecast_group: str
    air_region_code: str


def _load_catalog() -> dict[str, ForecastLocation]:
    raw = json.loads(
        Path(__file__).with_name("location_catalog.json").read_text(encoding="utf-8"),
        object_pairs_hook=_unique_mapping,
    )
    catalog = {
        rid: ForecastLocation(
            rid=rid,
            name=value["name"],
            label=value["label"],
            forecast_group=value["forecast_group"],
            air_region_code=value["air_region_code"],
        )
        for rid, value in raw.items()
    }
    return catalog


def _unique_mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of silently replacing catalog data."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"Location catalog contains a duplicate key: {key}")
        result[key] = value
    return result


LOCATIONS = _load_catalog()


def get_location(rid: str) -> ForecastLocation:
    """Return one supported catalog location."""
    try:
        return LOCATIONS[rid]
    except KeyError as err:
        raise ValueError(f"Unsupported location RID: {rid}") from err


def location_options() -> list[tuple[str, str]]:
    """Return Korean-label options in a predictable order."""
    return [
        (location.rid, location.label)
        for location in sorted(LOCATIONS.values(), key=lambda item: item.label)
    ]
