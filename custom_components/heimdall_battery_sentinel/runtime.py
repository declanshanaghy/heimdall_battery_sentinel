"""Runtime state and payload helpers for Heimdall Battery Sentinel."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_THRESHOLD,
    DATA_ALL_BATTERIES,
    DATA_LOW_BATTERIES,
    DATA_UNSUB,
    DATA_WS_SUBSCRIBERS,
    DEFAULT_THRESHOLD,
    DOMAIN,
)


def init_entry_runtime(hass: HomeAssistant, entry_id: str) -> None:
    """Initialize in-memory runtime state for a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry_id] = {
        DATA_ALL_BATTERIES: {},
        DATA_LOW_BATTERIES: {},
        DATA_UNSUB: [],
        DATA_WS_SUBSCRIBERS: [],
    }


def get_entry_runtime(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    """Return runtime state dictionary for a config entry."""
    return hass.data.get(DOMAIN, {}).get(entry_id, {})


def remove_entry_runtime(hass: HomeAssistant, entry_id: str) -> None:
    """Remove runtime state for a config entry."""
    hass.data.get(DOMAIN, {}).pop(entry_id, None)


def add_unsubscriber(hass: HomeAssistant, entry_id: str, unsub: Callable[[], None]) -> None:
    """Register a cleanup callback for a config entry."""
    get_entry_runtime(hass, entry_id).setdefault(DATA_UNSUB, []).append(unsub)


def unsubscribe_all(hass: HomeAssistant, entry_id: str) -> int:
    """Run and clear all registered cleanup callbacks for a config entry."""
    runtime = get_entry_runtime(hass, entry_id)
    unsubscribers = list(runtime.get(DATA_UNSUB, []))
    runtime[DATA_UNSUB] = []
    for unsub in unsubscribers:
        unsub()
    return len(unsubscribers)


def threshold_for_entry(entry: ConfigEntry) -> int:
    """Resolve active threshold for an entry."""
    return entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )


def get_primary_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the first Heimdall entry, if present."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def build_payload(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Build frontend payload from current runtime state."""
    entry_data = get_entry_runtime(hass, entry.entry_id)
    return {
        "all_batteries": list(entry_data.get(DATA_ALL_BATTERIES, {}).values()),
        "low_batteries": list(entry_data.get(DATA_LOW_BATTERIES, {}).values()),
        "threshold": threshold_for_entry(entry),
    }
