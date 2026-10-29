"""Probe the documented venue URL. Does not send orders or a guessed heartbeat."""

from __future__ import annotations

import sys

import httpx

URL = "http://192.168.65.157:3002/api/v1/stage"


def main() -> int:
    try:
        response = httpx.get(URL, timeout=3.0)
    except httpx.HTTPError as exc:
        print(f"unreachable: {exc.__class__.__name__}")
        print("The venue address is a private-network host. This machine is not on that network.")
        return 2
    print(f"reachable status={response.status_code} bytes={len(response.content)}")
    print("Body was not printed. Confirm the schema against the official PDF before trading.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
