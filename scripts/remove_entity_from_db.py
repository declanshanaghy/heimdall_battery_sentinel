#!/usr/bin/env python3
"""Remove a Home Assistant entity using Home Assistant APIs.

This script is intended to run on your local machine even when the DB lives on HA.
It uses:
1) recorder.purge_entities service to purge recorder data
2) entity registry delete endpoint (best effort)
3) DELETE /api/states/<entity_id> to clear runtime state
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import error, parse, request


def load_token() -> str | None:
    """Load HA token the same way deploy.sh does."""
    token = os.environ.get("HA_TOKEN", "").strip()
    if token:
        return token

    token_file = Path.home() / ".config" / "ha_token"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return None


def api_request(
    ha_url: str,
    token: str,
    method: str,
    path: str,
    payload: dict | list | None = None,
) -> tuple[int, str]:
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url=f"{ha_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers=headers,
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as http_err:
        return http_err.code, http_err.read().decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Request failed for {method} {path}: {exc}") from exc


def delete_entity_registry_entry(ha_url: str, token: str, entity_id: str) -> tuple[bool, str]:
    """Best-effort entity registry removal via REST endpoints if available."""
    quoted = parse.quote(entity_id, safe="")
    candidate_paths = [
        f"/api/config/entity_registry/entity/{quoted}",
        f"/api/config/entity_registry/entry/{quoted}",
    ]

    for path in candidate_paths:
        status, body = api_request(ha_url, token, "DELETE", path)
        if status in (200, 204):
            return True, f"Removed entity registry entry via {path}"
        if status == 404:
            continue
        return False, f"Registry delete failed ({status}) via {path}: {body}"

    return False, "No REST entity registry delete endpoint was available on this HA instance"


def entity_exists(ha_url: str, token: str, entity_id: str) -> tuple[bool, str]:
    """Check whether an entity exists in state machine or entity registry."""
    quoted = parse.quote(entity_id, safe="")

    state_status, state_body = api_request(ha_url, token, "GET", f"/api/states/{quoted}")
    if state_status == 200:
        return True, "found in state machine"
    if state_status not in (404,):
        return False, f"state lookup failed ({state_status}): {state_body}"

    # Fall back to entity registry lookup for entities with no current state.
    candidate_paths = [
        f"/api/config/entity_registry/entity/{quoted}",
        f"/api/config/entity_registry/entry/{quoted}",
    ]
    for path in candidate_paths:
        status, body = api_request(ha_url, token, "GET", path)
        if status == 200:
            return True, f"found in entity registry via {path}"
        if status == 404:
            continue
        return False, f"entity registry lookup failed ({status}) via {path}: {body}"

    return False, "not found in state machine or entity registry"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete a Home Assistant entity by entity_id via Home Assistant APIs."
    )
    parser.add_argument("entity_id", help="Entity ID to delete (for example: sensor.foo_battery)")
    parser.add_argument(
        "--ha-url",
        default=os.environ.get("HA_URL", "http://homeassistant:8123"),
        help="Home Assistant base URL (default: HA_URL env var or http://homeassistant:8123)",
    )
    args = parser.parse_args()

    entity_id = args.entity_id.strip()
    if not entity_id:
        print("Error: entity_id cannot be empty", file=sys.stderr)
        return 1

    token = load_token()
    if not token:
        print("Error: No token found.", file=sys.stderr)
        print("Set HA_TOKEN or create ~/.config/ha_token", file=sys.stderr)
        return 1

    ha_url = args.ha_url.rstrip("/")

    exists, exists_message = entity_exists(ha_url, token, entity_id)
    if not exists:
        print(f"Error: Entity '{entity_id}' was not found ({exists_message}).", file=sys.stderr)
        return 1

    quoted = parse.quote(entity_id, safe="")

    print("Planned API actions:")
    print("  1) Purge recorder history/statistics via recorder.purge_entities")
    print("  2) Remove entity registry entry (best effort)")
    print("  3) Delete current runtime state via DELETE /api/states/<entity_id>")
    print("")
    print(f"Home Assistant URL: {ha_url}")
    print(f"Entity ID:          {entity_id}")
    print(f"Entity check:       {exists_message}")
    print("")

    confirmation = input("Confirm deletion? Type 'Y' to continue: ").strip()
    if confirmation.lower() != "y":
        print("Aborted. No changes made.")
        return 0

    failures = 0

    purge_payload = {"entity_id": [entity_id], "keep_days": 0}
    purge_status, purge_body = api_request(
        ha_url,
        token,
        "POST",
        "/api/services/recorder/purge_entities",
        purge_payload,
    )
    if purge_status == 200:
        print("✓ Recorder purge request sent successfully.")
    else:
        failures += 1
        print(f"✗ Recorder purge failed ({purge_status}): {purge_body}")

    registry_ok, registry_msg = delete_entity_registry_entry(ha_url, token, entity_id)
    if registry_ok:
        print(f"✓ {registry_msg}")
    else:
        print(f"⚠ {registry_msg}")

    delete_status, delete_body = api_request(ha_url, token, "DELETE", f"/api/states/{quoted}")
    if delete_status in (200, 201):
        print("✓ Runtime state deleted.")
    elif delete_status == 404:
        print("✓ Runtime state already absent.")
    else:
        failures += 1
        print(f"✗ Runtime state delete failed ({delete_status}): {delete_body}")

    if failures:
        print("")
        print("Completed with errors. See messages above.")
        return 1

    print("")
    print("Completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
