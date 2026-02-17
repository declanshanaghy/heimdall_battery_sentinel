"""The Heimdall Battery Sentinel integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_THRESHOLD, DATA_LOW_BATTERIES, DEFAULT_THRESHOLD, DOMAIN
from .event_handlers import async_reevaluate_batteries, async_setup_event_handlers
from .runtime import init_entry_runtime, remove_entry_runtime, unsubscribe_all
from .views import async_register_panel_and_views, async_unregister_panel
from .websocket_handlers import register_websocket_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heimdall Battery Sentinel from a config entry."""
    _LOGGER.setLevel(logging.DEBUG)

    threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )
    _LOGGER.debug(
        "Setting up %s integration - Entry ID: %s, Threshold: %d%%",
        DOMAIN,
        entry.entry_id,
        threshold,
    )

    init_entry_runtime(hass, entry.entry_id)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await async_register_panel_and_views(hass)
    register_websocket_commands(hass)
    await async_setup_event_handlers(hass, entry)

    _LOGGER.info("Heimdall Battery Sentinel integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Heimdall Battery Sentinel integration - Entry ID: %s", entry.entry_id)

    listener_count = unsubscribe_all(hass, entry.entry_id)
    _LOGGER.debug("Unsubscribed %d event listeners", listener_count)

    low_battery_count = len(
        hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(DATA_LOW_BATTERIES, {})
    )
    _LOGGER.debug("Cleaning up data (%d low batteries tracked)", low_battery_count)
    remove_entry_runtime(hass, entry.entry_id)

    if not hass.data.get(DOMAIN):
        _LOGGER.debug("Removing Heimdall Battery Sentinel panel (last entry)")
        async_unregister_panel(hass)

    _LOGGER.info("Heimdall Battery Sentinel integration unloaded successfully")
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    new_threshold = entry.options.get(
        CONF_THRESHOLD,
        entry.data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD),
    )
    _LOGGER.info("Options updated - New threshold: %d%%", new_threshold)
    await async_reevaluate_batteries(hass, entry)
