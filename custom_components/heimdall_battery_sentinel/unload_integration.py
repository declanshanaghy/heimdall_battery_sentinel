#!/usr/bin/env python3
"""Unload Heimdall Battery Sentinel integration from Home Assistant."""

import json
import sys
import os

# Add parent directory to path to import from the same package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from const import DOMAIN
from api_utils import make_request

TOKEN = sys.argv[1] if len(sys.argv) > 1 else None
HA_URL = "http://localhost:8123"

if not TOKEN:
    print("Error: No access token provided")
    print("Usage: python3 unload_integration.py <token>")
    sys.exit(1)

try:
    # Get all config entries
    print(f"Fetching config entries from {HA_URL}...")
    status_code, response_body = make_request(
        f"{HA_URL}/api/config/config_entries/entry",
        method="GET",
        token=TOKEN
    )

    if status_code != 200:
        print(f"Failed to get config entries: HTTP {status_code}")
        print(f"Response: {response_body}")
        sys.exit(1)

    entries = json.loads(response_body)
    heimdall_battery_sentinel_entries = [e for e in entries if e.get("domain") == DOMAIN]

    if not heimdall_battery_sentinel_entries:
        print(f"No {DOMAIN} config entries found (integration not installed)")
        sys.exit(0)

    # Delete each entry
    print(f"Found {len(heimdall_battery_sentinel_entries)} {DOMAIN} config entries")
    for entry in heimdall_battery_sentinel_entries:
        entry_id = entry["entry_id"]
        entry_title = entry.get("title", "Untitled")
        print(f"  Removing config entry: {entry_id} ({entry_title})")

        delete_status, delete_body = make_request(
            f"{HA_URL}/api/config/config_entries/entry/{entry_id}",
            method="DELETE",
            token=TOKEN
        )

        if delete_status in (200, 204):
            print(f"  ✓ Removed entry {entry_id}")
        else:
            print(f"  ✗ Failed to remove entry {entry_id}: HTTP {delete_status}")
            print(f"  Response: {delete_body}")

    print(f"\nIntegration unloaded ({len(heimdall_battery_sentinel_entries)} entries removed)")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
