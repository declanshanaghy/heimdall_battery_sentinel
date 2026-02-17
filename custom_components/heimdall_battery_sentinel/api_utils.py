"""Utility functions for Home Assistant API interactions."""

import json
import urllib.request
import urllib.error


def make_request(url, method="GET", token=None, data=None):
    """Make an HTTP request using urllib.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, DELETE, etc.)
        token: Bearer token for authorization
        data: Optional dictionary to send as JSON body

    Returns:
        Tuple of (status_code, response_body)

    Raises:
        Exception: If there's a connection error
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            return status_code, response_body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except urllib.error.URLError as e:
        raise Exception(f"Connection error: {e.reason}")
