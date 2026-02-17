#!/usr/bin/env python3
"""Set up Heimdall Battery Sentinel integration in Home Assistant."""

import json
import sys
import os

# Add parent directory to path to import from the same package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from const import DOMAIN, DEFAULT_THRESHOLD
from api_utils import make_request

TOKEN = sys.argv[1] if len(sys.argv) > 1 else None
THRESHOLD = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_THRESHOLD
HA_URL = "http://localhost:8123"

if not TOKEN:
    print("Error: No access token provided")
    print("Usage: python3 setup_integration.py <token> [threshold]")
    sys.exit(1)

try:
    print(f"Setting up {DOMAIN} integration...")

    # Step 1: Start the config flow
    print("  Starting config flow...")
    status, response_body = make_request(
        f"{HA_URL}/api/config/config_entries/flow",
        method="POST",
        token=TOKEN,
        data={"handler": DOMAIN}
    )

    if status not in (200, 201):
        print(f"  ✗ Failed to start config flow: HTTP {status}")
        print(f"  Response: {response_body}")
        sys.exit(1)

    flow_response = json.loads(response_body)
    flow_id = flow_response.get("flow_id")

    if not flow_id:
        print(f"  ✗ No flow_id in response")
        print(f"  Response: {response_body}")
        sys.exit(1)

    print(f"  Config flow started: {flow_id}")

    # Step 2: Submit the configuration (threshold)
    print(f"  Submitting configuration (threshold: {THRESHOLD}%)...")
    status, response_body = make_request(
        f"{HA_URL}/api/config/config_entries/flow/{flow_id}",
        method="POST",
        token=TOKEN,
        data={"threshold": THRESHOLD}
    )

    if status not in (200, 201):
        print(f"  ✗ Failed to complete config flow: HTTP {status}")
        print(f"  Response: {response_body}")
        sys.exit(1)

    result = json.loads(response_body)

    if result.get("type") == "create_entry":
        entry_id = result.get("result", {}).get("entry_id")
        print(f"  ✓ Integration set up successfully!")
        print(f"  Entry ID: {entry_id}")
        print(f"  Threshold: {THRESHOLD}%")
    else:
        print(f"  ✗ Unexpected result type: {result.get('type')}")
        print(f"  Response: {response_body}")
        sys.exit(1)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
