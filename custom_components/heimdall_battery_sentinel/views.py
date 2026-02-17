"""HTTP views and panel registration for Heimdall Battery Sentinel."""
from __future__ import annotations

import logging
import os

from aiohttp import web
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_ICON, PANEL_NAME, PANEL_TITLE

_LOGGER = logging.getLogger(__name__)


async def async_register_panel_and_views(hass: HomeAssistant) -> None:
    """Register static views, then register the sidebar panel."""
    _LOGGER.debug("Registering Heimdall Battery Sentinel panel and views")

    panel_js_path = hass.config.path(f"custom_components/{DOMAIN}/frontend/panel.js")
    panel_html_path = hass.config.path(f"custom_components/{DOMAIN}/frontend/panel.html")

    hass.http.register_view(BatteryMonitorPanelJSView(panel_js_path))
    hass.http.register_view(BatteryMonitorPanelHTMLView(panel_html_path))

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


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel."""
    async_remove_panel(hass, PANEL_NAME)


class _StaticFileView(HomeAssistantView):
    """Base view to serve static files from disk."""

    requires_auth = False
    content_type: str

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    async def get(self, request):
        def read_file() -> str | None:
            if not os.path.exists(self.file_path):
                return None
            with open(self.file_path, "r", encoding="utf-8") as file:
                return file.read()

        content = await request.app["hass"].async_add_executor_job(read_file)
        if content is None:
            return web.Response(status=404, text="File not found")

        return web.Response(
            text=content,
            content_type=self.content_type,
            headers={"Cache-Control": "no-store"},
        )


class BatteryMonitorPanelJSView(_StaticFileView):
    """View to serve the panel JavaScript file."""

    url = f"/api/{DOMAIN}/panel.js"
    name = f"api:{DOMAIN}:panel.js"
    content_type = "application/javascript"


class BatteryMonitorPanelHTMLView(_StaticFileView):
    """View to serve the panel HTML file."""

    url = f"/api/{DOMAIN}/panel.html"
    name = f"api:{DOMAIN}:panel.html"
    content_type = "text/html"
