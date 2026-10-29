#!/usr/bin/env python3
"""Extract MANTHAN portal API docs on the venue network.

Reads MANTHAN_PORTAL_PASSWORD from the environment. It does not print the
password, session cookies, or Authorization headers. It does not submit orders.

Run this on a machine that can open http://192.168.65.157:3003:

    pip install -r scripts/requirements-portal.txt
    python -m playwright install chromium
    export MANTHAN_PORTAL_PASSWORD='...'
    python scripts/extract_portal_contracts.py

Output stays in var/portal-extract/, which is gitignored. Review it before
copying any contract into the trading engine. OpenAPI documents are converted
with backend/app/api/models.py catalog_from_openapi. Prose pages are saved as
text and are not turned into guessed field lists.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "var" / "portal-extract"
USERNAME = os.environ.get("MANTHAN_PORTAL_USERNAME", "MN2615")
PORTAL = os.environ.get("MANTHAN_PORTAL_URL", "http://192.168.65.157:3003").rstrip("/")
PASSWORD = os.environ.get("MANTHAN_PORTAL_PASSWORD", "")

DOC_HINTS = ("api", "doc", "swagger", "openapi", "kafka", "rule", "heartbeat", "order", "portfolio", "stock")
PROBE_PATHS = (
    "/",
    "/docs",
    "/api-docs",
    "/swagger",
    "/swagger/index.html",
    "/openapi.json",
    "/api/openapi.json",
    "/v3/api-docs",
    "/redoc",
)
SECRET_LINE = re.compile(
    r"(?i)(password|authorization|set-cookie|bearer\s+[A-Za-z0-9._\-+/=]+|eyJ[A-Za-z0-9_\-]{8,})"
)


def redact_text(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if SECRET_LINE.search(line):
            kept.append("[redacted]")
        else:
            kept.append(line)
    return "\n".join(kept)


def main() -> int:
    if not PASSWORD:
        print("MANTHAN_PORTAL_PASSWORD is not set. Export it in the shell. Do not put it in a file.", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install Playwright from scripts/requirements-portal.txt and run playwright install chromium.", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    pages: list[dict] = []
    openapi: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(20000)
        try:
            page.goto(PORTAL, wait_until="domcontentloaded")
        except Exception as exc:
            print(f"Portal unreachable: {type(exc).__name__}", file=sys.stderr)
            browser.close()
            return 3
        if not _login(page):
            print("Login form was not found or login did not leave the password field.", file=sys.stderr)
            browser.close()
            return 4
        if page.locator("input[type=password]").count():
            print("Password field is still visible. Login was not accepted.", file=sys.stderr)
            browser.close()
            return 4

        seeds = {PORTAL + path for path in PROBE_PATHS}
        for link in page.locator("a").all():
            href = link.get_attribute("href") or ""
            label = (link.inner_text() or "").strip().lower()
            absolute = urljoin(page.url, href)
            if _same_host(absolute) and any(hint in (absolute + " " + label).lower() for hint in DOC_HINTS):
                seeds.add(absolute.split("#")[0])

        for url in list(seeds)[:30]:
            record = _read_page(page, url)
            if record is None:
                continue
            pages.append(record)
            if record.get("openapi"):
                openapi.append(record["openapi"])

        browser.close()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    extract = {
        "extracted_at": stamp,
        "portal_url": PORTAL,
        "username": USERNAME,
        "pages": [{k: v for k, v in item.items() if k != "openapi"} for item in pages],
        "openapi_count": len(openapi),
    }
    (OUT / "pages.json").write_text(json.dumps(extract, indent=2), encoding="utf-8")
    for index, spec in enumerate(openapi):
        (OUT / f"openapi-{index}.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Saved {len(pages)} pages and {len(openapi)} OpenAPI documents under var/portal-extract/")
    print("Review that directory. Do not commit it until secrets are confirmed absent.")
    if not openapi:
        print("No OpenAPI document was found. Field lists remain MISSING until one is saved.")
    return 0


def _same_host(url: str) -> bool:
    parsed = urlparse(url)
    portal = urlparse(PORTAL)
    return parsed.scheme in {"http", "https"} and parsed.netloc == portal.netloc


def _login(page) -> bool:
    password = page.locator("input[type=password]")
    if password.count() == 0:
        return page.locator("input[type=password]").count() == 0 and page.url != PORTAL
    text_inputs = page.locator("input:not([type=password]):not([type=hidden]):not([type=submit])")
    if text_inputs.count() == 0:
        return False
    text_inputs.first.fill(USERNAME)
    password.first.fill(PASSWORD)
    button = page.locator("button[type=submit], input[type=submit], button")
    if button.count() == 0:
        password.first.press("Enter")
    else:
        button.first.click()
    page.wait_for_timeout(1500)
    return True


def _read_page(page, url: str) -> dict | None:
    try:
        response = page.goto(url, wait_until="domcontentloaded")
    except Exception:
        return None
    if response is None:
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" in content_type:
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
            return {"url": url, "title": "openapi", "text": "", "openapi": data}
        return None
    if page.locator("input[type=password]").count():
        return None
    title = page.title()
    text = redact_text(page.locator("body").inner_text()[:30000])
    blocks = []
    for node in page.locator("pre, code").all()[:20]:
        snippet = redact_text(node.inner_text()[:4000])
        if snippet:
            blocks.append(snippet)
    return {"url": url, "title": title, "text": text, "code_blocks": blocks}


if __name__ == "__main__":
    raise SystemExit(main())
