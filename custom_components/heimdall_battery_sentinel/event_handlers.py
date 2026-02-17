"""Event handling for battery discovery and state updates."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback

from .const import DATA_ALL_BATTERIES, DATA_LOW_BATTERIES
from .runtime import (
    add_unsubscriber,
    get_entry_runtime,
    threshold_for_entry,
)
from .websocket_handlers import notify_frontend_update

_LOGGER = logging.getLogger(__name__)


async def async_setup_event_handlers(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up battery tracking and event listeners for an entry."""
    battery_entities = _discover_battery_entities(hass)
    _LOGGER.info("Discovered %d battery entities", len(battery_entities))
    await _async_evaluate_batteries(hass, entry, battery_entities)

    @callback
    def async_battery_state_listener(event: Event) -> None:
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not entity_id:
            return

        runtime = get_entry_runtime(hass, entry.entry_id)
        is_tracked = entity_id in runtime.get(DATA_ALL_BATTERIES, {})
        is_battery_now = bool(new_state and _is_battery_state(new_state))

        if is_battery_now and new_state is not None:
            _LOGGER.debug(
                "Battery state change event: %s (old: %s, new: %s)",
                entity_id,
                old_state.state if old_state else "None",
                new_state.state,
            )
            _handle_battery_state_change(hass, entry, entity_id, new_state)
        elif is_tracked:
            _LOGGER.debug("Entity %s is no longer a battery entity or has no state", entity_id)
            _remove_battery_entity(hass, entry, entity_id, reason="removed_or_not_battery")

    add_unsubscriber(
        hass,
        entry.entry_id,
        hass.bus.async_listen(EVENT_STATE_CHANGED, async_battery_state_listener),
    )

    @callback
    def async_entity_registry_updated(event: Event) -> None:
        action = event.data.get("action")
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("Entity registry update: action=%s, entity_id=%s", action, entity_id)
        if not entity_id:
            return

        if action == "create":
            if _is_battery_entity(hass, entity_id):
                _LOGGER.info("New battery entity discovered: %s", entity_id)
                state = hass.states.get(entity_id)
                if state:
                    _handle_battery_state_change(hass, entry, entity_id, state)
        elif action == "remove":
            _LOGGER.info("Battery entity removed from registry: %s", entity_id)
            _remove_battery_entity(hass, entry, entity_id, reason="entity_removed")
        elif action == "update":
            state = hass.states.get(entity_id)
            if state and _is_battery_state(state):
                _handle_battery_state_change(hass, entry, entity_id, state)
            else:
                _remove_battery_entity(hass, entry, entity_id, reason="entity_updated_not_battery")

    add_unsubscriber(
        hass,
        entry.entry_id,
        hass.bus.async_listen("entity_registry_updated", async_entity_registry_updated),
    )


async def async_reevaluate_batteries(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-evaluate tracked batteries after options updates."""
    _LOGGER.debug("Re-evaluating all battery entities")
    await _async_evaluate_batteries(hass, entry, _discover_battery_entities(hass))
    _LOGGER.debug("Re-evaluation complete")


def _discover_battery_entities(hass: HomeAssistant) -> list[str]:
    battery_entities: list[str] = []
    _LOGGER.debug("Starting battery entity discovery")
    for state in hass.states.async_all():
        if _is_battery_state(state):
            battery_entities.append(state.entity_id)
            _LOGGER.debug(
                "Battery entity discovered: %s (name: %s, state: %s)",
                state.entity_id,
                state.attributes.get("friendly_name", state.entity_id),
                state.state,
            )
    _LOGGER.debug("Battery entity discovery complete: found %d entities", len(battery_entities))
    return battery_entities


def _is_battery_entity(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return _is_battery_state(state)


def _is_battery_state(state: Any) -> bool:
    return state is not None and state.attributes.get(ATTR_DEVICE_CLASS) == "battery"


async def _async_evaluate_batteries(hass: HomeAssistant, entry: ConfigEntry, entity_ids: list[str]) -> None:
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state:
            _handle_battery_state_change(hass, entry, entity_id, state)


@callback
def _remove_battery_entity(hass: HomeAssistant, entry: ConfigEntry, entity_id: str, reason: str) -> None:
    runtime = get_entry_runtime(hass, entry.entry_id)
    all_batteries = runtime.get(DATA_ALL_BATTERIES, {})
    low_batteries = runtime.get(DATA_LOW_BATTERIES, {})

    removed_from_all = all_batteries.pop(entity_id, None) is not None
    removed_from_low = low_batteries.pop(entity_id, None) is not None
    if removed_from_all or removed_from_low:
        _LOGGER.debug(
            "Removed entity %s from tracking (all=%s, low=%s)",
            entity_id,
            removed_from_all,
            removed_from_low,
        )
        notify_frontend_update(hass, entry, reason=reason, entity_id=entity_id)


@callback
def _handle_battery_state_change(
    hass: HomeAssistant, entry: ConfigEntry, entity_id: str, state: Any
) -> None:
    friendly_name = state.attributes.get("friendly_name", entity_id)
    _LOGGER.debug(
        "Processing battery state for %s (name: %s, state: %s)",
        entity_id,
        friendly_name,
        state.state,
    )

    entity_details = {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": str(state.last_changed),
        "last_updated": str(state.last_updated),
    }
    _LOGGER.debug("Entity JSON dump: %s", json.dumps(entity_details, indent=2))

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        _remove_battery_entity(hass, entry, entity_id, reason="state_unavailable_or_unknown")
        return

    battery_level = None
    try:
        battery_level = float(state.state)
    except (ValueError, TypeError):
        battery_attr = state.attributes.get("battery")
        if battery_attr is not None:
            try:
                battery_level = float(battery_attr)
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "Entity %s has battery attribute but can't parse as float: %s",
                    entity_id,
                    battery_attr,
                )

    if battery_level is None:
        _remove_battery_entity(hass, entry, entity_id, reason="non_numeric_battery")
        return

    threshold = threshold_for_entry(entry)
    runtime = get_entry_runtime(hass, entry.entry_id)
    all_batteries = runtime.get(DATA_ALL_BATTERIES, {})
    low_batteries = runtime.get(DATA_LOW_BATTERIES, {})
    old_all_data = all_batteries.get(entity_id)
    old_low_data = low_batteries.get(entity_id)

    battery_data = {
        "entity_id": entity_id,
        "battery_level": battery_level,
        "friendly_name": friendly_name,
        "state_value": state.state,
        "unit": state.attributes.get("unit_of_measurement", ""),
        "is_low": battery_level <= threshold,
        "last_changed": str(state.last_changed),
        "last_updated": str(state.last_updated),
    }
    all_batteries[entity_id] = battery_data

    if battery_level <= threshold:
        was_already_low = entity_id in low_batteries
        low_batteries[entity_id] = battery_data
        if not was_already_low:
            _LOGGER.warning("Low battery detected: %s at %.1f%%", friendly_name, battery_level)
    elif entity_id in low_batteries:
        low_batteries.pop(entity_id)
        _LOGGER.info(
            "Battery recovered: %s at %.1f%% (threshold: %d%%)",
            friendly_name,
            battery_level,
            threshold,
        )

    if old_all_data != all_batteries.get(entity_id) or old_low_data != low_batteries.get(entity_id):
        notify_frontend_update(hass, entry, reason="state_update", entity_id=entity_id)
