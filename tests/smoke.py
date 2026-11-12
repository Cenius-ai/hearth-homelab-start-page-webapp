#!/usr/bin/env python3
"""Live smoke test for a running Hearth instance.

    python3 -m app.server          # in one terminal
    python3 tests/smoke.py         # in another

Prints one PASS/FAIL line per flow and exits non-zero if anything failed.
Set HEARTH_URL to test a different origin (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402

BASE_URL = os.environ.get("HEARTH_URL", "http://127.0.0.1:8000").rstrip("/")

failures: list[str] = []


def report(ok: bool, step: str, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {step}{f' — {detail}' if detail else ''}")
    if not ok:
        failures.append(step)


def call(opener, method: str, path: str, payload: dict | None = None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read()
            body = json.loads(raw) if raw else None
            return response.status, body
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = None
        return error.code, body


def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(config.DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def main() -> int:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    status, body = call(opener, "GET", "/healthz")
    report(status == 200 and (body or {}).get("status") == "ok", "/healthz liveness", f"HTTP {status}")

    status, body = call(
        opener,
        "POST",
        "/api/auth/login",
        {"email": config.DEMO_EMAIL, "password": config.DEMO_PASSWORD},
    )
    report(status == 200, "demo login (cenius@cenius.ai)", f"HTTP {status}")

    status, body = call(
        opener,
        "POST",
        "/api/auth/login",
        {"email": config.DEMO_EMAIL, "password": "***REDACTED-SECRET***"},
    )
    report(
        status == 401,
        "wrong password is rejected",
        f"HTTP {status} {'' if status == 401 else 'server accepted a bad password'}",
    )

    status, payload = call(opener, "GET", "/api/bootstrap")
    services = (payload or {}).get("services") or []
    report(
        status == 200 and bool(payload.get("groups")) and bool(services),
        "bootstrap payload",
        f"{len(services)} services in {len(payload.get('groups') or [])} groups",
    )

    status, created = call(
        opener,
        "POST",
        "/api/services",
        {"name": "Smoke Test Tile", "url": "http://smoke.lan:9999", "category_id": 1, "icon": "🧪"},
    )
    service = (created or {}).get("service") or {}
    service_id = service.get("id")
    report(
        status == 201 and service.get("host_port") == "smoke.lan:9999",
        "service create",
        f"HTTP {status} host:port={service.get('host_port')}",
    )

    _, payload = call(opener, "GET", "/api/bootstrap")
    visible = any(item["id"] == service_id for item in payload.get("services") or [])
    report(visible, "created service appears in bootstrap")

    # Give the new tile a health check and a layout row, then delete it and prove
    # the child rows went with it.
    call(opener, "POST", f"/api/services/{service_id}/check")
    order = [item["id"] for item in payload.get("services") or []]
    call(opener, "PUT", "/api/layout", {"service_ids": order})

    status, _ = call(opener, "DELETE", f"/api/services/{service_id}")
    report(status == 204, "service delete", f"HTTP {status}")

    with db_connection() as connection:
        checks = connection.execute(
            "SELECT COUNT(*) FROM health_checks WHERE service_id = ?", (service_id,)
        ).fetchone()[0]
        layout = connection.execute(
            "SELECT COUNT(*) FROM layout_items WHERE service_id = ?", (service_id,)
        ).fetchone()[0]
    report(checks == 0 and layout == 0, "delete cascaded health checks and layout rows")

    status, created = call(
        opener, "POST", "/api/bookmarks", {"label": "Smoke Bookmark", "url": "http://smoke.lan/"}
    )
    bookmark_id = ((created or {}).get("bookmark") or {}).get("id")
    report(status == 201, "bookmark add", f"HTTP {status}")

    _, payload = call(opener, "GET", "/api/bootstrap")
    present = any(item["id"] == bookmark_id for item in payload.get("bookmarks") or [])
    report(present, "bookmark appears in bootstrap")

    status, _ = call(opener, "DELETE", f"/api/bookmarks/{bookmark_id}")
    _, payload = call(opener, "GET", "/api/bootstrap")
    gone = all(item["id"] != bookmark_id for item in payload.get("bookmarks") or [])
    report(status == 204 and gone, "bookmark delete", f"HTTP {status}")

    _, payload = call(opener, "GET", "/api/bootstrap")
    saved_order = [item["id"] for item in payload.get("services") or []]
    reversed_order = list(reversed(saved_order))
    status, _ = call(opener, "PUT", "/api/layout", {"service_ids": reversed_order})
    _, reloaded = call(opener, "GET", "/api/bootstrap")
    persisted = [item["id"] for item in reloaded.get("services") or []]
    report(
        status == 200 and persisted == reversed_order,
        "layout save survives a reload",
        f"HTTP {status}",
    )
    call(opener, "PUT", "/api/layout", {"service_ids": saved_order})

    # Force the current session to expire and prove the next call is refused.
    with db_connection() as connection:
        connection.execute("UPDATE sessions SET expires_at = '2020-01-01T00:00:00+00:00'")
        connection.commit()
    status, body = call(opener, "GET", "/api/bootstrap")
    report(
        status == 401,
        "expired session is rejected",
        f"HTTP {status} {(body or {}).get('error', '')}".strip(),
    )

    print()
    if failures:
        print(f"SMOKE FAILED: {len(failures)} step(s) — {', '.join(failures)}")
        return 1
    print("SMOKE PASSED: every flow works against", BASE_URL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
