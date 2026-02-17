## Technical Architecture

### Integration Structure

```
custom_components/heimdall_battery_sentinel/
├── __init__.py          # Integration setup, event listeners
├── manifest.json        # Integration metadata
├── config_flow.py       # UI configuration flow + options flow
├── const.py             # Constants (domain, defaults, config keys)
├── strings.json         # UI strings for config flow
├── translations/
│   └── en.json          # English translations
└── frontend/
    └── panel.js         # Custom panel (LitElement web component)
```

### manifest.json

```json
{
  "domain": "heimdall_battery_sentinel",
  "name": "Heimdall Battery Sentinel",
  "codeowners": [],
  "config_flow": true,
  "documentation": "",
  "iot_class": "local_push",
  "version": "1.0.0",
  "requirements": [],
  "dependencies": ["frontend"]
}
```

Key choices:
- `iot_class: local_push` — the integration reacts to state change events rather than polling.
- `dependencies: ["frontend"]` — required for registering the custom panel.
- No external `requirements` — the integration uses only Home Assistant's built-in APIs.

### Data Flow

```
HA State Machine
       │
       ▼
  state_changed event
       │
       ▼
  Heimdall Battery Sentinel
  (event listener)
       │
       ├── level ≤ threshold → Store in panel data
       │
       └── level > threshold → Remove from panel data

       Panel reads data store on load / via WebSocket
```

### Custom Panel Registration

The integration registers its panel in `__init__.py` during setup using `hass.components.frontend.async_register_built_in_panel()` or the `panel_custom` service. The panel is a LitElement web component that:

1. Connects to Home Assistant via the `hass` object passed as a property.
2. Reads entity states and history data to render the device table.
3. Updates reactively when `hass` property changes.

### Configuration Storage

- **Config entry:** Stores the threshold value via Home Assistant's config entries system.
- **Runtime state:** Maintains an in-memory dictionary of currently-flagged devices, keyed by entity ID. This is rebuilt from current states on Home Assistant startup.
