# ⚔️ Heimdall Battery Sentinel

> *"From his hall Himinbjörg, the all-seeing guardian watches over the realms, alert to the faintest warning..."*

Heimdall stands eternal watch over your Home Assistant batteries, ever vigilant for devices whose power wanes. Like the Norse guardian who needed less sleep than a bird and could see a hundred miles by day or night, Heimdall monitors all your battery-powered devices and sounds the alarm when their energy falls below your chosen threshold.

## 🛡️ The Guardian's Powers

- **⚡ All-Seeing Vision** - Automatically discovers and tracks every battery entity in your realm
- **🔔 Swift Warnings** - Alerts you immediately when batteries drop below your threshold
- **📊 The Watch List** - Beautiful panel displaying all tracked devices and their power levels
- **🎯 Event-Driven** - No polling, no waste - Heimdall reacts instantly to state changes
- **🎨 Theme Aware** - Adapts to your Home Assistant theme (light, dark, or custom)
- **⚙️ Configurable Threshold** - Set your own power level for warnings (default: 20%)

## 🏰 Installation

### Prerequisites
- Home Assistant
- SSH access to your Home Assistant instance
- A long-lived access token

### Deploy Heimdall to Your Realm

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd heimdall_battery_sentinel
   ```

2. **Set your access token:**
   ```bash
   # Option 1: Environment variable (temporary)
   export HA_TOKEN="your_long_lived_token"

   # Option 2: Config file (persistent)
   echo "your_long_lived_token" > ~/.config/ha_token
   ```

3. **Deploy:**
   ```bash
   # Fast deployment (upload only)
   ./scripts/deploy.sh

   # Full deployment (with restart and setup)
   ./scripts/deploy.sh --restart
   ```

## 🗡️ Configuration

After deployment, Heimdall can be configured through the Home Assistant UI:

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for "Heimdall Battery Sentinel"
4. Set your desired alert threshold (default: 20%)

## 📜 The Sentinel's Watch

Once configured, find Heimdall's panel in your Home Assistant sidebar. The panel displays:

- **⚠️ Low Battery Devices** - Batteries below your threshold
- **📋 All Tracked Battery Entities** - Complete view of monitored batteries (collapsed by default; click **Show Table** to load and display)

Each device shows:
- Entity ID
- Friendly name
- Current battery level (color-coded)

## 🎭 Technical Architecture

Heimdall is built with the wisdom of the ages:

```
custom_components/heimdall_battery_sentinel/
├── __init__.py              # Integration lifecycle orchestration
├── const.py                 # Configuration constants
├── runtime.py               # Shared runtime state + payload helpers
├── event_handlers.py        # Battery discovery + event/state handling
├── websocket_handlers.py    # WebSocket command handlers + subscriptions
├── views.py                 # Static file + REST/panel view registration
├── config_flow.py           # Setup and options flow
├── manifest.json            # Integration metadata
├── strings.json             # UI strings
├── api_utils.py             # Shared API utilities
├── setup_integration.py     # Auto-setup script
├── unload_integration.py    # Auto-unload script
└── frontend/
    ├── panel.js             # LitElement UI component
    └── panel.html           # Panel container
```

### The Guardian's Methods

Heimdall identifies battery entities with precision:
- **Primary Method**: Only entities with `device_class: battery` are monitored
- Event-driven architecture with zero polling overhead
- Automatic cleanup when batteries recover

## 🌟 Features in Detail

### Event-Driven Architecture
Unlike lesser sentinels who must constantly check for changes, Heimdall listens for Home Assistant state change events. When a battery's power shifts, Heimdall knows immediately - no wasted energy, no delays.

### Theme Integration
Heimdall respects your realm's appearance. Whether you prefer the brightness of Álfheimr or the darkness of Svartálfaheimr, the panel adapts seamlessly to your chosen theme through CSS custom properties inherited from your Home Assistant profile.

### APIs
Heimdall exposes a REST endpoint for battery data and WebSocket commands for panel reads/updates.

REST endpoint:
```
GET /api/heimdall_battery_sentinel/data
```

Returns:
```json
{
  "all_batteries": [...],
  "low_batteries": [...],
  "threshold": 20
}
```

WebSocket commands:
- `heimdall_battery_sentinel/get_low_batteries`
- `heimdall_battery_sentinel/get_all_batteries`
- `heimdall_battery_sentinel/subscribe_updates`

## 🔧 Development

### Fast Iteration
For rapid development, use the fast deployment mode:
```bash
./scripts/deploy.sh
```

This uploads code changes without restarting Home Assistant.
Frontend changes apply after a panel refresh; backend changes apply after Home Assistant restart.

### Full Deployment
When you need to test the complete integration lifecycle:
```bash
./scripts/deploy.sh --restart
```

This unloads the old integration, restarts HA, waits for it to come back online, and sets up the integration fresh.

### Remove Stale Entity History
If you need to remove a stale entity from Home Assistant using HA APIs:

```bash
./scripts/remove_entity_from_db.py sensor.spa_cover_moving_battery
```

By default it targets `http://homeassistant:8123`.  
Use `--ha-url` if your HA URL is different:

```bash
./scripts/remove_entity_from_db.py --ha-url http://192.168.1.50:8123 sensor.spa_cover_moving_battery
```

Token loading matches deploy.sh: it uses `HA_TOKEN` first, then `~/.config/ha_token`.
The script requires a confirmation prompt (`Y`/`y`) before it deletes anything.

### Clean Stale MQTT Retained Topics
To inspect and clean stale retained MQTT topics:

```bash
./scripts/cleanup_mqtt_retained.py
```

Defaults:
- Host: `mqtt`
- Port: `1883`
- User: `mqtt`
- Scope: `homeassistant/` prefix

Password loading:
1. `HA_MQTT_PASSWD`
2. `~/.config/ha_mqtt_passwd`

Delete mode prompts per topic (`y` to delete, anything else to skip):

```bash
./scripts/cleanup_mqtt_retained.py --execute
```

## 🎯 Customization

### Threshold
Adjust the warning threshold at any time:
1. Settings → Devices & Services
2. Find "Heimdall Battery Sentinel"
3. Click Configure
4. Adjust the threshold percentage

### Panel Icon
The panel icon is currently `mdi:battery-20`. To change it, modify `PANEL_ICON` in `const.py`.

## 🌈 Color Coding

Heimdall uses colors to convey urgency:
- 🔴 **Red** (≤5%): Critical - immediate attention required
- 🟠 **Orange** (≤threshold): Warning - battery running low
- 🟢 **Green** (>threshold): Healthy - all is well

## 📖 Etymology

**Heimdall** (Old Norse: Heimdallr) is the vigilant guardian of Ásgarðr in Norse mythology. He possesses extraordinary senses:
- Can see for hundreds of miles
- Can hear grass growing and wool growing on sheep
- Requires less sleep than a bird
- Will sound the Gjallarhorn to warn of Ragnarök

These qualities make Heimdall the perfect name for a Heimdall Battery Sentineling system that must watch constantly and alert immediately.

## 🤝 Contributing

Contributions to strengthen Heimdall's watch are welcome! Whether you're fixing bugs, adding features, or improving documentation, your efforts help protect realms everywhere from the darkness of dead batteries.

## 📜 License

This integration is released into the public domain. Use it freely to guard your own realm.

## 🙏 Acknowledgments

Built with:
- **Home Assistant** - The foundation of the smart home realm
- **LitElement** - For reactive UI components
- **Python** - The language of the ancients
- **Norse Mythology** - For inspiration and naming

---

*May Heimdall watch over your batteries, and may your devices never go dark* ⚡🛡️
