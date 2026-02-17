"""The Heimdall Battery Sentinel integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.components import websocket_api
from aiohttp import web
import os

from .const import (
    CONF_THRESHOLD,
    DATA_ALL_BATTERIES,
    DATA_LOW_BATTERIES,
    DATA_UNSUB,
    DEFAULT_THRESHOLD,
    DOMAIN,
    PANEL_ICON,
    PANEL_NAME,
    PANEL_TITLE,
    PANEL_URL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heimdall Battery Sentinel from a config entry."""
    # Enable debug logging for this integration
    _LOGGER.setLevel(logging.DEBUG)

    threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )
    _LOGGER.debug(
        f"Setting up {DOMAIN} integration - Entry ID: %s, Threshold: %d%%",
        entry.entry_id,
        threshold,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_ALL_BATTERIES: {},
        DATA_LOW_BATTERIES: {},
        DATA_UNSUB: [],
    }

    # Register the options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Register the custom panel
    await _async_register_panel(hass)

    # Register WebSocket API (only once)
    ws_key = f"{DOMAIN}_ws_registered"
    if not hass.data.get(ws_key, False):
        _LOGGER.info("Registering WebSocket API command: heimdall_battery_sentinel/get_data")
        try:
            websocket_api.async_register_command(hass, websocket_get_battery_data)
            _LOGGER.info("WebSocket API command registered successfully")
            hass.data[ws_key] = True
        except Exception as e:
            _LOGGER.error("Failed to register WebSocket API command: %s", e, exc_info=True)
    else:
        _LOGGER.debug("WebSocket API command already registered, skipping")

    # Discover and monitor battery entities
    await _async_setup_heimdall_battery_sentineling(hass, entry)

    _LOGGER.info("Heimdall Battery Sentinel integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Heimdall Battery Sentinel integration - Entry ID: %s", entry.entry_id)

    # Unsubscribe from all listeners
    listener_count = len(hass.data[DOMAIN][entry.entry_id][DATA_UNSUB])
    _LOGGER.debug("Unsubscribing %d event listeners", listener_count)
    for unsub in hass.data[DOMAIN][entry.entry_id][DATA_UNSUB]:
        unsub()

    # Clean up data
    low_battery_count = len(hass.data[DOMAIN][entry.entry_id][DATA_LOW_BATTERIES])
    _LOGGER.debug("Cleaning up data (%d low batteries tracked)", low_battery_count)
    hass.data[DOMAIN].pop(entry.entry_id)

    # Remove panel if this is the last entry
    if not hass.data[DOMAIN]:
        _LOGGER.debug("Removing Heimdall Battery Sentinel panel (last entry)")
        async_remove_panel(hass, PANEL_NAME)

    _LOGGER.info("Heimdall Battery Sentinel integration unloaded successfully")
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    new_threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )
    _LOGGER.info("Options updated - New threshold: %d%%", new_threshold)
    # Re-evaluate all battery entities with the new threshold
    await _async_reevaluate_batteries(hass, entry)


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the custom panel."""
    _LOGGER.debug("Registering Heimdall Battery Sentinel panel")

    # Register views to serve static files
    panel_js_path = hass.config.path(f"custom_components/{DOMAIN}/frontend/panel.js")
    panel_html_path = hass.config.path(f"custom_components/{DOMAIN}/frontend/panel.html")

    _LOGGER.debug("Registering view for panel.js: %s", panel_js_path)
    hass.http.register_view(BatteryMonitorPanelJSView(panel_js_path))

    _LOGGER.debug("Registering view for panel.html: %s", panel_html_path)
    hass.http.register_view(BatteryMonitorPanelHTMLView(panel_html_path))

    # Register the data API view
    _LOGGER.debug("Registering view for battery data API")
    hass.http.register_view(BatteryMonitorDataView())

    # Register the panel
    _LOGGER.debug("Registering panel: %s (title: %s, icon: %s)", PANEL_NAME, PANEL_TITLE, PANEL_ICON)
    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_NAME,
        config={"url": f"/api/{DOMAIN}/panel.html"},
        require_admin=False,
    )
    _LOGGER.info("Heimdall Battery Sentinel panel registered successfully")


class BatteryMonitorPanelJSView(HomeAssistantView):
    """View to serve the panel JavaScript file."""

    requires_auth = False
    url = f"/api/{DOMAIN}/panel.js"
    name = f"api:{DOMAIN}:panel.js"

    def __init__(self, file_path: str) -> None:
        """Initialize the view."""
        self.file_path = file_path

    async def get(self, request):
        """Serve the JavaScript file."""
        def read_file():
            """Read file in executor."""
            if not os.path.exists(self.file_path):
                return None
            with open(self.file_path, "r", encoding="utf-8") as file:
                return file.read()

        content = await request.app["hass"].async_add_executor_job(read_file)

        if content is None:
            return web.Response(status=404, text="File not found")

        return web.Response(
            text=content,
            content_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )


class BatteryMonitorPanelHTMLView(HomeAssistantView):
    """View to serve the panel HTML file."""

    requires_auth = False
    url = f"/api/{DOMAIN}/panel.html"
    name = f"api:{DOMAIN}:panel.html"

    def __init__(self, file_path: str) -> None:
        """Initialize the view."""
        self.file_path = file_path

    async def get(self, request):
        """Serve the HTML file."""
        def read_file():
            """Read file in executor."""
            if not os.path.exists(self.file_path):
                return None
            with open(self.file_path, "r", encoding="utf-8") as file:
                return file.read()

        content = await request.app["hass"].async_add_executor_job(read_file)

        if content is None:
            return web.Response(status=404, text="File not found")

        return web.Response(
            text=content,
            content_type="text/html",
            headers={"Cache-Control": "no-store"},
        )


class BatteryMonitorDataView(HomeAssistantView):
    """View to serve battery data via REST API."""

    requires_auth = False
    url = f"/api/{DOMAIN}/data"
    name = f"api:{DOMAIN}:data"

    async def get(self, request):
        """Return battery data as JSON."""
        hass = request.app["hass"]

        _LOGGER.debug("REST API: /api/%s/data called", DOMAIN)

        # Get the first config entry
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return web.json_response(
                {"error": "No Heimdall Battery Sentinel configuration found"},
                status=404
            )

        entry = entries[0]
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

        all_batteries = entry_data.get(DATA_ALL_BATTERIES, {})
        low_batteries = entry_data.get(DATA_LOW_BATTERIES, {})
        threshold = entry.options.get(
            CONF_THRESHOLD,
            entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
        )

        # Convert to lists for easier frontend handling
        all_batteries_list = list(all_batteries.values())
        low_batteries_list = list(low_batteries.values())

        _LOGGER.debug(
            "REST API: Returning %d all batteries, %d low batteries (threshold: %d%%)",
            len(all_batteries_list),
            len(low_batteries_list),
            threshold,
        )

        return web.json_response({
            "all_batteries": all_batteries_list,
            "low_batteries": low_batteries_list,
            "threshold": threshold,
        })


async def _async_setup_heimdall_battery_sentineling(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Set up Heimdall Battery Sentineling for all battery entities."""
    entity_reg = er.async_get(hass)

    # Discover all battery entities
    battery_entities = _discover_battery_entities(hass, entity_reg)
    _LOGGER.info("Discovered %d battery entities", len(battery_entities))

    # Initial evaluation of all battery entities
    await _async_evaluate_batteries(hass, entry, battery_entities)

    # Set up state change listener for all battery entities
    @callback
    def async_battery_state_listener(event: Event) -> None:
        """Handle battery state changes."""
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if new_state is None:
            return

        _LOGGER.debug(
            "Battery state change event: %s (old: %s, new: %s)",
            entity_id,
            old_state.state if old_state else "None",
            new_state.state,
        )

        _handle_battery_state_change(hass, entry, entity_id, new_state)

    # Track state changes for all battery entities
    unsub = async_track_state_change_event(hass, battery_entities, async_battery_state_listener)
    hass.data[DOMAIN][entry.entry_id][DATA_UNSUB].append(unsub)

    # Also listen for new entities being added
    @callback
    def async_entity_registry_updated(event: Event) -> None:
        """Handle entity registry updates."""
        action = event.data.get("action")
        entity_id = event.data.get("entity_id")

        _LOGGER.debug("Entity registry update: action=%s, entity_id=%s", action, entity_id)

        if action == "create":
            if _is_battery_entity(hass, entity_reg, entity_id):
                _LOGGER.info("New battery entity discovered: %s", entity_id)
                # Evaluate the new entity
                state = hass.states.get(entity_id)
                if state:
                    _handle_battery_state_change(hass, entry, entity_id, state)
                else:
                    _LOGGER.debug("New battery entity %s has no state yet", entity_id)

    # Listen for entity registry updates
    unsub = hass.bus.async_listen("entity_registry_updated", async_entity_registry_updated)
    hass.data[DOMAIN][entry.entry_id][DATA_UNSUB].append(unsub)


def _discover_battery_entities(
    hass: HomeAssistant, entity_reg: er.EntityRegistry
) -> list[str]:
    """Discover all battery entities."""
    battery_entities = []
    _LOGGER.debug("Starting battery entity discovery")

    for state in hass.states.async_all():
        entity_id = state.entity_id

        if _is_battery_entity(hass, entity_reg, entity_id):
            battery_entities.append(entity_id)
            _LOGGER.debug(
                "Battery entity discovered: %s (name: %s, state: %s)",
                entity_id,
                state.attributes.get("friendly_name", entity_id),
                state.state,
            )

    _LOGGER.debug("Battery entity discovery complete: found %d entities", len(battery_entities))
    return battery_entities


def _is_battery_entity(
    hass: HomeAssistant, entity_reg: er.EntityRegistry, entity_id: str
) -> bool:
    """Check if an entity is a battery entity.

    Only entities with device_class='battery' are considered battery entities.
    """
    state = hass.states.get(entity_id)
    if not state:
        return False

    # Only check for device_class: battery
    device_class = state.attributes.get(ATTR_DEVICE_CLASS)
    _LOGGER.debug("Checking entity %s - device_class: %s", entity_id, device_class)

    if device_class == "battery":
        _LOGGER.debug(
            "✓ Entity %s identified as battery (device_class=battery)",
            entity_id,
        )
        return True

    _LOGGER.debug("✗ Entity %s not a battery entity (device_class: %s)", entity_id, device_class)
    return False


async def _async_evaluate_batteries(
    hass: HomeAssistant, entry: ConfigEntry, entity_ids: list[str]
) -> None:
    """Evaluate all battery entities."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state:
            _handle_battery_state_change(hass, entry, entity_id, state)


async def _async_reevaluate_batteries(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Re-evaluate all battery entities with updated threshold."""
    _LOGGER.debug("Re-evaluating all battery entities")
    entity_reg = er.async_get(hass)
    battery_entities = _discover_battery_entities(hass, entity_reg)
    await _async_evaluate_batteries(hass, entry, battery_entities)
    _LOGGER.debug("Re-evaluation complete")


@callback
def _handle_battery_state_change(
    hass: HomeAssistant, entry: ConfigEntry, entity_id: str, state: Any
) -> None:
    """Handle battery state change."""
    import json

    friendly_name = state.attributes.get("friendly_name", entity_id)

    _LOGGER.debug(
        "Processing battery state for %s (name: %s, state: %s)",
        entity_id,
        friendly_name,
        state.state,
    )

    # Dump full entity details as JSON for debugging
    entity_details = {
        "entity_id": entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": str(state.last_changed),
        "last_updated": str(state.last_updated),
    }
    _LOGGER.debug("Entity JSON dump: %s", json.dumps(entity_details, indent=2))

    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        _LOGGER.debug("Entity %s is %s, removing from tracking", entity_id, state.state)
        # Remove from low batteries if present
        low_batteries = hass.data[DOMAIN][entry.entry_id][DATA_LOW_BATTERIES]
        if entity_id in low_batteries:
            low_batteries.pop(entity_id)
            _LOGGER.debug("Removed %s from low battery list (unavailable/unknown)", entity_id)
        return

    # Get battery level - try multiple sources
    battery_level = None

    # Try parsing state as battery level
    _LOGGER.debug("Checking 'state' field for battery level. value is '%s'", state.state)
    try:
        battery_level = float(state.state)
        _LOGGER.debug(
            "✓ Successfully parsed battery level from state: %.1f",
            battery_level,
        )
    except (ValueError, TypeError):
        _LOGGER.debug("✗ State field cannot be parsed as float, trying battery attribute")
        # Try to get battery from attributes
        battery_attr = state.attributes.get("battery")
        _LOGGER.debug("Checking battery attribute field: %s", battery_attr)
        if battery_attr is not None:
            try:
                battery_level = float(battery_attr)
                _LOGGER.debug(
                    "✓ Successfully parsed battery level from attribute: %.1f",
                    battery_level,
                )
            except (ValueError, TypeError):
                _LOGGER.debug(
                    "✗ Entity %s has battery attribute but can't parse as float: %s",
                    entity_id,
                    battery_attr,
                )

    if battery_level is None:
        _LOGGER.debug("✗ Entity %s has no parsable battery level from any source", entity_id)
        return

    _LOGGER.debug(
        "Entity %s battery level: %.1f%%",
        entity_id,
        battery_level,
    )

    # Get threshold from options or data
    threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )

    all_batteries = hass.data[DOMAIN][entry.entry_id][DATA_ALL_BATTERIES]
    low_batteries = hass.data[DOMAIN][entry.entry_id][DATA_LOW_BATTERIES]

    # Always track in all_batteries
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
        # Add or update in low batteries
        was_already_low = entity_id in low_batteries
        low_batteries[entity_id] = battery_data
        _LOGGER.debug(
            "Battery %s: %s (name: %s) at %.1f%% (threshold: %d%%)",
            "still low" if was_already_low else "now low",
            entity_id,
            friendly_name,
            battery_level,
            threshold,
        )
        if not was_already_low:
            _LOGGER.warning(
                "Low battery detected: %s at %.1f%%",
                friendly_name,
                battery_level,
            )
    else:
        # Remove from low batteries if present
        if entity_id in low_batteries:
            low_batteries.pop(entity_id)
            _LOGGER.info(
                "Battery recovered: %s at %.1f%% (threshold: %d%%)",
                friendly_name,
                battery_level,
                threshold,
            )
        else:
            _LOGGER.debug(
                "Battery OK: %s at %.1f%% (threshold: %d%%)",
                entity_id,
                battery_level,
                threshold,
            )


@websocket_api.websocket_command(
    {
        "type": "heimdall_battery_sentinel/get_data",
    }
)
@callback
def websocket_get_battery_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get battery data websocket command."""
    _LOGGER.debug("WebSocket: heimdall_battery_sentinel/get_data called")

    # Get the first config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "no_config", "No Heimdall Battery Sentinel configuration found")
        return

    entry = entries[0]
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    all_batteries = entry_data.get(DATA_ALL_BATTERIES, {})
    low_batteries = entry_data.get(DATA_LOW_BATTERIES, {})
    threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )

    # Convert to lists for easier frontend handling
    all_batteries_list = list(all_batteries.values())
    low_batteries_list = list(low_batteries.values())

    _LOGGER.debug(
        "WebSocket: Returning %d all batteries, %d low batteries (threshold: %d%%)",
        len(all_batteries_list),
        len(low_batteries_list),
        threshold,
    )

    connection.send_result(
        msg["id"],
        {
            "all_batteries": all_batteries_list,
            "low_batteries": low_batteries_list,
            "threshold": threshold,
        },
    )


