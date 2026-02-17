#!/usr/bin/env python3
"""Clean up retained MQTT topics on a Mosquitto broker."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


DEFAULT_HOST = "mqtt"
DEFAULT_PORT = 1883
DEFAULT_USER = "mqtt"
DEFAULT_PASSWORD_FILE = Path("~/.config/ha_mqtt_passwd").expanduser()
DEFAULT_PREFIX = "homeassistant/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean up retained MQTT topics.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Broker hostname (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Broker port (default: {DEFAULT_PORT})")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"Broker username (default: {DEFAULT_USER})")
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Topic prefix to clean (repeatable), e.g. --prefix zigbee2mqtt/",
    )
    parser.add_argument(
        "--all-retained",
        action="store_true",
        help="Target all retained topics on the broker",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Inactivity timeout in seconds while scanning retained topics (default: 2)",
    )
    parser.add_argument(
        "--max-scan-seconds",
        type=float,
        default=20.0,
        help="Hard limit for topic scan duration in seconds (default: 20)",
    )
    parser.add_argument("--execute", action="store_true", help="Actually delete retained topics")
    parser.add_argument("--yes", action="store_true", help="Reserved flag (currently no-op)")
    return parser.parse_args()


def load_password() -> str | None:
    password = os.environ.get("HA_MQTT_PASSWD", "").strip()
    if password:
        return password

    if DEFAULT_PASSWORD_FILE.exists():
        return DEFAULT_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return None


def import_mqtt():
    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: paho-mqtt. Install with: pip install paho-mqtt"
        ) from exc
    return mqtt


def new_client(mqtt, user: str, password: str):
    # Compatible across paho-mqtt major versions.
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        client = mqtt.Client()
    client.username_pw_set(user, password)
    return client


def is_connack_success(reason_code) -> bool:
    """Handle paho-mqtt v1/v2 reason_code variations."""
    if reason_code is None:
        return False

    if isinstance(reason_code, (int, float)):
        return int(reason_code) == 0

    value = getattr(reason_code, "value", None)
    if isinstance(value, (int, float)):
        return int(value) == 0

    try:
        return reason_code == 0
    except Exception:
        pass

    return str(reason_code).strip().lower() in {"0", "success"}


def scan_retained_topics(
    mqtt,
    host: str,
    port: int,
    user: str,
    password: str,
    timeout_seconds: float,
    max_scan_seconds: float,
) -> dict[str, str]:
    topics: dict[str, str] = {}
    connected = False
    connection_error: str | None = None
    last_activity = time.monotonic()

    client = new_client(mqtt, user, password)

    def on_connect(client, _userdata, _flags, reason_code, _properties=None):
        nonlocal connected, connection_error, last_activity
        try:
            if not is_connack_success(reason_code):
                connection_error = f"MQTT connect failed with code {reason_code}"
                return
            connected = True
            last_activity = time.monotonic()
            client.subscribe("#", qos=0)
        except Exception as err:
            connection_error = f"MQTT connect callback failed: {err}"

    def on_message(_client, _userdata, msg):
        nonlocal last_activity
        last_activity = time.monotonic()
        if msg.retain:
            payload = msg.payload.decode("utf-8", errors="replace") if msg.payload else ""
            topics[msg.topic] = payload

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(host, port, keepalive=30)
    client.loop_start()
    try:
        start = time.monotonic()
        while True:
            now = time.monotonic()
            if connection_error:
                raise RuntimeError(connection_error)
            if connected and (now - last_activity) >= timeout_seconds:
                break
            if (now - start) >= max_scan_seconds:
                break
            time.sleep(0.05)
    finally:
        client.disconnect()
        client.loop_stop()

    return topics


def filter_topics(topics: dict[str, str], prefixes: list[str], all_retained: bool) -> list[str]:
    if all_retained:
        return sorted(topics.keys())
    return sorted(
        topic for topic in topics.keys() if any(topic.startswith(prefix) for prefix in prefixes)
    )


def _row_from_topic_and_payload(topic: str, payload: str) -> list[str]:
    entity_name = ""
    manufacturer = ""
    model = ""

    if payload:
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                entity_name = str(data.get("name", "") or "")
                device = data.get("device", {})
                if isinstance(device, dict):
                    manufacturer = str(device.get("manufacturer", "") or "")
                    model = str(device.get("model", "") or "")
                    if not entity_name:
                        entity_name = str(device.get("name", "") or "")
        except Exception:
            pass

    device = " ".join(part for part in [manufacturer, model] if part).strip()
    return [topic, entity_name, device]


def print_entities_table(target_topics: list[str], topics_map: dict[str, str]) -> None:
    headers = ["topic", "entity name", "device"]
    rows = [_row_from_topic_and_payload(topic, topics_map.get(topic, "")) for topic in target_topics]

    table_rows = [headers] + rows
    widths = [max(len(str(row[i])) for row in table_rows) for i in range(len(headers))]

    def format_row(row: list[str]) -> str:
        return "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)) + " |"

    divider = "|-" + "-|-".join("-" * w for w in widths) + "-|"

    print("Entities:")
    print(format_row(headers))
    print(divider)
    for row in rows:
        print(format_row(row))


def delete_topics(
    mqtt,
    host: str,
    port: int,
    user: str,
    password: str,
    target_topics: list[str],
    topics_map: dict[str, str],
) -> int:
    client = new_client(mqtt, user, password)
    client.connect(host, port, keepalive=30)
    client.loop_start()
    deleted = 0
    try:
        for index, topic in enumerate(target_topics, start=1):
            row = _row_from_topic_and_payload(topic, topics_map.get(topic, ""))
            print("")
            print(f"[{index}/{len(target_topics)}] Ready to delete retained topic:")
            print(f"  topic: {row[0]}")
            print(f"  entity name: {row[1] or '(unknown)'}")
            print(f"  device: {row[2] or '(unknown)'}")
            confirm = input("Delete this topic? [y/N]: ").strip().lower()
            if confirm != "y":
                print("  Skipped.")
                continue
            info = client.publish(topic, payload=b"", qos=0, retain=True)
            info.wait_for_publish()
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"Failed to delete retained topic '{topic}', rc={info.rc}")
            deleted += 1
            print("  Deleted.")
    finally:
        client.disconnect()
        client.loop_stop()
    return deleted


def main() -> int:
    args = parse_args()
    prefixes = args.prefix[:] if args.prefix else []
    if not args.all_retained and not prefixes:
        prefixes = [DEFAULT_PREFIX]

    password = load_password()
    if not password:
        print(
            f"Error: MQTT password not found. Set HA_MQTT_PASSWD or create {DEFAULT_PASSWORD_FILE}",
            file=sys.stderr,
        )
        return 1

    try:
        mqtt = import_mqtt()
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print(f"Scanning retained topics from {args.user}@{args.host}:{args.port} ...")
    try:
        all_topics = scan_retained_topics(
            mqtt,
            host=args.host,
            port=args.port,
            user=args.user,
            password=password,
            timeout_seconds=args.timeout,
            max_scan_seconds=args.max_scan_seconds,
        )
    except Exception as err:
        print(f"Error while scanning retained topics: {err}", file=sys.stderr)
        return 1

    print(f"Found {len(all_topics)} retained topic(s) total.")
    targets = filter_topics(all_topics, prefixes, args.all_retained)
    if not targets:
        print("No retained topics matched the selected scope. Nothing to do.")
        return 0

    print("")
    print(f"Target retained topic(s): {len(targets)}")
    if args.all_retained:
        print("Scope: ALL retained topics")
    else:
        print("Scope prefixes:")
        for prefix in prefixes:
            print(f"  - {prefix}")
    print("")
    print_entities_table(targets, all_topics)

    if not args.execute:
        print("")
        print("Dry run only. Re-run with --execute to delete these retained topics.")
        return 0

    try:
        deleted = delete_topics(
            mqtt,
            host=args.host,
            port=args.port,
            user=args.user,
            password=password,
            target_topics=targets,
            topics_map=all_topics,
        )
    except Exception as err:
        print(f"Error while deleting topics: {err}", file=sys.stderr)
        return 1

    print(f"Deleted {deleted} retained topic(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        raise SystemExit(130)
