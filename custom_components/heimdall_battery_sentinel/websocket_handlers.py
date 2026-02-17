"""WebSocket command handlers for Heimdall Battery Sentinel."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DATA_LOW_BATTERIES, DATA_WS_SUBSCRIBERS, DOMAIN
from .runtime import build_payload, get_entry_runtime, get_primary_entry

_LOGGER = logging.getLogger(__name__)
_WS_REGISTERED_KEY = f"{DOMAIN}_ws_registered"


def register_websocket_commands(hass: HomeAssistant) -> None:
    """Register websocket commands once per HA instance."""
    if hass.data.get(_WS_REGISTERED_KEY, False):
        _LOGGER.debug("WebSocket API commands already registered, skipping")
        return

    _LOGGER.info("Registering WebSocket API commands")
    websocket_api.async_register_command(hass, websocket_get_low_batteries)
    websocket_api.async_register_command(hass, websocket_get_all_batteries)
    websocket_api.async_register_command(hass, websocket_subscribe_battery_updates)
    hass.data[_WS_REGISTERED_KEY] = True


@callback
def notify_frontend_update(
    hass: HomeAssistant,
    entry: ConfigEntry,
    reason: str,
    entity_id: str,
) -> None:
    """Push a battery payload update to all websocket subscribers."""
    entry_data = get_entry_runtime(hass, entry.entry_id)
    subscribers = list(entry_data.get(DATA_WS_SUBSCRIBERS, []))
    if not subscribers:
        return

    payload = build_payload(hass, entry)
    payload["reason"] = reason
    payload["entity_id"] = entity_id

    stale_subscribers: list[tuple[websocket_api.ActiveConnection, int]] = []
    for connection, subscription_id in subscribers:
        try:
            connection.send_message(websocket_api.event_message(subscription_id, payload))
        except Exception:
            stale_subscribers.append((connection, subscription_id))

    if stale_subscribers:
        entry_data[DATA_WS_SUBSCRIBERS] = [
            sub for sub in entry_data.get(DATA_WS_SUBSCRIBERS, []) if sub not in stale_subscribers
        ]


@websocket_api.websocket_command({"type": "heimdall_battery_sentinel/get_low_batteries"})
@callback
def websocket_get_low_batteries(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return low battery payload to a websocket client."""
    _LOGGER.debug("WebSocket: heimdall_battery_sentinel/get_low_batteries called")
    entry = get_primary_entry(hass)
    if not entry:
        connection.send_error(msg["id"], "no_config", "No Heimdall Battery Sentinel configuration found")
        return

    entry_data = get_entry_runtime(hass, entry.entry_id)
    payload = build_payload(hass, entry)
    payload.pop("all_batteries", None)
    payload["low_batteries"] = list(entry_data.get(DATA_LOW_BATTERIES, {}).values())
    _LOGGER.debug(
        "WebSocket: Returning %d low batteries (threshold: %d%%)",
        len(payload["low_batteries"]),
        payload["threshold"],
    )
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command({"type": "heimdall_battery_sentinel/get_all_batteries"})
@callback
def websocket_get_all_batteries(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return all tracked battery payload to a websocket client."""
    _LOGGER.debug("WebSocket: heimdall_battery_sentinel/get_all_batteries called")
    entry = get_primary_entry(hass)
    if not entry:
        connection.send_error(msg["id"], "no_config", "No Heimdall Battery Sentinel configuration found")
        return

    payload = build_payload(hass, entry)
    payload.pop("low_batteries", None)
    _LOGGER.debug(
        "WebSocket: Returning %d all batteries (threshold: %d%%)",
        len(payload["all_batteries"]),
        payload["threshold"],
    )
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command({"type": "heimdall_battery_sentinel/subscribe_updates"})
@callback
def websocket_subscribe_battery_updates(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe a websocket client to battery payload update events."""
    entry = get_primary_entry(hass)
    if not entry:
        connection.send_error(msg["id"], "no_config", "No Heimdall Battery Sentinel configuration found")
        return

    entry_data = get_entry_runtime(hass, entry.entry_id)
    subscribers = entry_data.setdefault(DATA_WS_SUBSCRIBERS, [])
    subscriber = (connection, msg["id"])
    subscribers.append(subscriber)

    @callback
    def _unsubscribe() -> None:
        runtime = get_entry_runtime(hass, entry.entry_id)
        subs = runtime.get(DATA_WS_SUBSCRIBERS, [])
        if subscriber in subs:
            subs.remove(subscriber)

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"])
