# Heimdall Battery Sentinel — Product Requirements Document

## Overview

Heimdall Battery Sentinel is a custom Home Assistant integration that automatically discovers all battery-powered devices, tracks their charge levels, and alerts the user when batteries drop below a configurable threshold. It provides a dedicated sidebar panel showing devices that need attention, along with historical drain trends.

## Problem Statement

Home Assistant users with many battery-powered devices (sensors, locks, remotes, etc.) have no centralized way to see which batteries are running low. Battery levels are scattered across individual device pages, making it easy to miss a dying sensor until it stops reporting. This integration solves that by surfacing low-battery devices in one place, proactively.

## Goals

- Automatically discover all entities that report a battery level — no manual device selection or filtering required.
- Alert the user when any device drops below a global threshold (default: 10%).
- Provide a dedicated panel in the Home Assistant sidebar listing all low-battery devices with current level, location, and historical drain trend.
- Silently remove devices from the panel once their battery is replaced (charge rises above threshold).

## Non-Goals

- Per-device threshold overrides.
- Device include/exclude lists or area-based filtering.
- Push notifications or persistent notifications (the panel is the primary UX surface).
- Performance optimization, automated testing, or disaster recovery (homebrew project scope).

---

## User Experience

### Configuration

The integration supports **both** UI-based config flow and YAML configuration.

**Config Flow (UI)**

Users add the integration via *Settings → Devices & Services → Add Integration → Heimdall Battery Sentinel*. The setup wizard presents a single step:

| Field             | Type    | Default | Description                                      |
|-------------------|---------|---------|--------------------------------------------------|
| Battery threshold | Integer | 10      | Percentage at or below which a device is flagged. |

After setup, the integration begins monitoring immediately.

**YAML Configuration**

```yaml
heimdall_battery_sentinel:
  threshold: 10
```

The YAML path allows headless or version-controlled setups. If both config entry and YAML exist, the config entry takes precedence.

**Options Flow**

Users can update the threshold at any time via *Settings → Devices & Services → Heimdall Battery Sentinel → Configure* without restarting Home Assistant.

### Sidebar Panel

The integration registers a custom panel in the Home Assistant sidebar:

- **Sidebar title:** "Batteries"
- **Sidebar icon:** `mdi:battery-alert`
- **URL path:** `/battery-monitor`

#### Panel Layout

The panel displays a list/table of devices currently at or below the threshold. Each row shows:

| Column            | Description                                                                 |
|-------------------|-----------------------------------------------------------------------------|
| Device name       | Friendly name of the device as registered in Home Assistant.                |
| Battery level     | Current percentage, with a color-coded icon (red ≤ 5%, orange ≤ threshold). |
| Area              | The Home Assistant area the device is assigned to, if any.                  |
| Trend             | A small sparkline or mini-chart showing battery level over the last 30 days.|

**Empty state:** When no devices are below the threshold, the panel shows a friendly message such as "All batteries are healthy" with a green checkmark icon.

**Sorting:** Devices are sorted by battery level ascending (most critical first).

#### Historical Trend

The trend column uses Home Assistant's built-in `history` data to render a compact visualization of the battery drain over time. This helps users anticipate which devices will need replacement soon, even among those already flagged.

### Device Recovery

When a device's battery level rises back above the threshold (e.g., battery replaced), it is **silently removed** from the panel. No notification is sent. The panel always reflects the current state of low-battery devices only.

### Device Discovery

The integration discovers battery-powered devices by scanning for entities that meet **any** of the following criteria:

1. Entities with `device_class: battery` (the standard approach).
2. Entities whose `entity_id` contains `battery` and reports a numeric percentage state.
3. Device diagnostic entities that report battery level as an attribute.

Discovery is **automatic and continuous** — new devices added to Home Assistant are picked up without reconfiguration.

### Event-Driven Architecture

The integration does **not** poll on a timer. Instead, it listens for `state_changed` events on all discovered battery entities. When a state change is received:

1. If the new battery level is **at or below** the threshold → add/update the device in the panel's data store.
2. If the new battery level is **above** the threshold → remove the device from the panel's data store.

This approach is lightweight and reacts in real time to state updates from devices.

