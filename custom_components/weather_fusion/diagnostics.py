"""Shareable diagnostics without location selectors, URLs or provider payloads."""

from .const import DOMAIN, FORECAST_KEYS, METRIC_KEYS


async def async_get_config_entry_diagnostics(hass, entry):
    manager = hass.data[DOMAIN][entry.entry_id]
    return {
        "integration_version": manager.software_version,
        "entry_version": entry.version,
        "status": manager.status(),
        "sources": {
            group: {
                "last_success": source.attributes.get("last_success")
                or (source.last_reported.isoformat() if source.last_reported else None),
                "source_date": source.attributes.get("source_date"),
                "source_updated_at": source.attributes.get("source_updated_at"),
                "fetch_error": bool(source.attributes.get("last_error")),
                "using_cached_data": bool(source.attributes.get("using_cached_data")),
                "missing_or_invalid_fields": list(source.value_errors),
                "available_fields": list(source.numeric),
                "forecast_dates": [item.day.isoformat() for item in source.daily],
                "forecast_times": [item.time.isoformat() for item in source.hourly],
            }
            for group, source in manager.source_snapshots().items()
        },
        "selected_sources": {
            key: list(manager.metric(key).selected_sources) for key in METRIC_KEYS
        },
        "rejected_sources": {
            key: {
                source: reason.split(":", 1)[0]
                for source, reason in manager.metric(key).rejected_sources.items()
            }
            for key in METRIC_KEYS
        },
        "missing_metrics": [
            key for key in METRIC_KEYS if manager.metric(key).value is None
        ],
        "missing_forecasts": [
            key for key in FORECAST_KEYS if manager.forecast(key).value is None
        ],
    }
