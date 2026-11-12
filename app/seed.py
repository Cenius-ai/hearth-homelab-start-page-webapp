"""Idempotent boot seed.

Running this twice must not duplicate anything: every insert is guarded by a
lookup first. It is safe to call from the server boot path (`run_seed()`) and as
a standalone entrypoint (`python -m app.seed`), which exits without binding a
port.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Iterable

from . import config
from .db import init_db, insert, open_db, query_one
from .formatting import iso, utcnow
from .security import hash_password

CATEGORIES: list[tuple[str, int]] = [
    ("Media", 0),
    ("Network", 1),
    ("Infrastructure", 2),
    ("Observability", 3),
]

# name, url, category, icon, sort_order
SERVICES: list[tuple[str, str, str, str, int]] = [
    ("Jellyfin", "http://jellyfin.lan:8096", "Media", "🎬", 0),
    ("Navidrome", "http://music.lan:4533", "Media", "🎧", 1),
    ("Router", "http://192.168.1.1", "Network", "📶", 0),
    ("Pi-hole", "http://192.168.1.9/admin", "Network", "🛡️", 1),
    ("Proxmox VE", "https://proxmox.lan:8006", "Infrastructure", "🖥️", 0),
    ("Home Assistant", "http://homeassistant.lan:8123", "Infrastructure", "🏠", 1),
    ("Grafana", "http://grafana.lan:3000", "Observability", "📈", 0),
]

# Health history: service name -> [(status, latency_ms, message, minutes_ago)].
# Home Assistant is deliberately left unchecked so the grey "Never checked"
# state is visible on a first run.
HEALTH_HISTORY: dict[str, list[tuple[str, int | None, str, int]]] = {
    "Jellyfin": [("up", 42, "HTTP 200", 4), ("up", 51, "HTTP 200", 19)],
    "Navidrome": [("up", 88, "HTTP 200", 7)],
    "Router": [("up", 12, "HTTP 200", 2), ("down", None, "timeout", 34)],
    "Pi-hole": [("down", None, "connection refused", 11), ("up", 31, "HTTP 200", 68)],
    "Proxmox VE": [("up", 133, "HTTP 200", 23)],
    "Grafana": [("up", 61, "HTTP 200", 9), ("up", 74, "HTTP 200", 41)],
}

BOOKMARKS: dict[str, list[tuple[str, str]]] = {
    config.DEMO_EMAIL: [
        ("Proxmox VE", "https://proxmox.lan:8006"),
        ("Grafana", "http://grafana.lan:3000"),
        ("Uptime Kuma", "http://uptime.lan:3001"),
        ("GitHub", "https://github.com"),
    ],
    config.SECOND_DEMO_EMAIL: [
        ("Pi-hole admin", "http://192.168.1.9/admin"),
        ("Jellyfin", "http://jellyfin.lan:8096"),
    ],
}

DEMO_ACCOUNTS: list[tuple[str, str]] = [
    (config.DEMO_EMAIL, config.DEMO_PASSWORD),
    (config.SECOND_DEMO_EMAIL, config.SECOND_DEMO_PASSWORD),
]


async def ensure_user(db, email: str, password: str) -> int:
    normalized = email.strip().lower()
    row = await query_one(db, "SELECT id FROM users WHERE email = ?", (normalized,))
    if row is not None:
        return int(row["id"])
    password_hash, salt = hash_password(password)
    return await insert(
        db,
        "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
        (normalized, password_hash, salt, iso(utcnow())),
    )


async def ensure_category(db, name: str, sort_order: int) -> int:
    row = await query_one(db, "SELECT id FROM categories WHERE name = ?", (name,))
    if row is not None:
        return int(row["id"])
    return await insert(
        db, "INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, sort_order)
    )


async def ensure_service(
    db, *, name: str, url: str, category_id: int, icon: str, sort_order: int
) -> tuple[int, bool]:
    row = await query_one(db, "SELECT id, url FROM services WHERE name = ?", (name,))
    if row is not None:
        service_id = int(row["id"])
        if row["url"] != url:
            # e.g. the app was restarted on a different port: keep the self-probe honest.
            now = iso(utcnow())
            await db.execute("UPDATE services SET url = ?, updated_at = ? WHERE id = ?", (url, now, service_id))
            await db.commit()
        return service_id, False
    now = iso(utcnow())
    service_id = await insert(
        db,
        "INSERT INTO services (name, url, category_id, icon, sort_order, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, url, category_id, icon, sort_order, now, now),
    )
    return service_id, True


async def ensure_health_history(db, service_id: int, history: Iterable[tuple[str, int | None, str, int]]) -> int:
    row = await query_one(db, "SELECT COUNT(*) AS total FROM health_checks WHERE service_id = ?", (service_id,))
    if row is not None and int(row["total"]) > 0:
        return 0
    now = utcnow()
    rows = [
        (service_id, status, latency, message, iso(now - timedelta(minutes=minutes_ago)))
        for status, latency, message, minutes_ago in history
    ]
    if rows:
        await db.executemany(
            "INSERT INTO health_checks (service_id, status, latency_ms, message, checked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        await db.commit()
    return len(rows)


async def ensure_bookmark(db, user_id: int, label: str, url: str, sort_order: int) -> bool:
    row = await query_one(db, "SELECT id FROM bookmarks WHERE user_id = ? AND label = ?", (user_id, label))
    if row is not None:
        return False
    await insert(
        db,
        "INSERT INTO bookmarks (user_id, label, url, sort_order, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, label, url, sort_order, iso(utcnow())),
    )
    return True


async def seed_database(db) -> dict[str, Any]:
    """Seed everything that is missing. Returns a small summary for the logs."""
    summary = {"users": 0, "categories": 0, "services": 0, "checks": 0, "bookmarks": 0}

    user_ids: dict[str, int] = {}
    for email, password in DEMO_ACCOUNTS:
        before = await query_one(db, "SELECT id FROM users WHERE email = ?", (email.strip().lower(),))
        user_ids[email] = await ensure_user(db, email, password)
        if before is None:
            summary["users"] += 1

    category_ids: dict[str, int] = {}
    for name, sort_order in CATEGORIES:
        before = await query_one(db, "SELECT id FROM categories WHERE name = ?", (name,))
        category_ids[name] = await ensure_category(db, name, sort_order)
        if before is None:
            summary["categories"] += 1

    service_ids: dict[str, int] = {}
    for name, url, category, icon, sort_order in SERVICES:
        service_id, created = await ensure_service(
            db,
            name=name,
            url=url,
            category_id=category_ids[category],
            icon=icon,
            sort_order=sort_order,
        )
        service_ids[name] = service_id
        if created:
            summary["services"] += 1

    # The app's own liveness route, so the self-probe tile reflects reality.
    self_probe_id, created = await ensure_service(
        db,
        name=config.SELF_PROBE_SERVICE_NAME,
        url=config.self_probe_url(),
        category_id=category_ids["Observability"],
        icon="🔥",
        sort_order=1,
    )
    service_ids[config.SELF_PROBE_SERVICE_NAME] = self_probe_id
    if created:
        summary["services"] += 1

    for name, history in HEALTH_HISTORY.items():
        service_id = service_ids.get(name)
        if service_id is None:
            continue
        summary["checks"] += await ensure_health_history(db, service_id, history)

    for email, bookmarks in BOOKMARKS.items():
        user_id = user_ids.get(email)
        if user_id is None:
            continue
        for index, (label, url) in enumerate(bookmarks):
            if await ensure_bookmark(db, user_id, label, url, index):
                summary["bookmarks"] += 1

    return summary


async def run_seed() -> dict[str, Any]:
    await init_db()
    async with open_db() as db:
        return await seed_database(db)


async def _main() -> None:
    summary = await run_seed()
    print(
        "Seed complete: "
        f"{summary['users']} new users, {summary['categories']} new categories, "
        f"{summary['services']} new services, {summary['checks']} new health checks, "
        f"{summary['bookmarks']} new bookmarks."
    )
    print(f"Demo login: {config.DEMO_EMAIL} / {config.DEMO_PASSWORD}")
    print(f"Second account: {config.SECOND_DEMO_EMAIL} / {config.SECOND_DEMO_PASSWORD}")
    print(f"Database: {config.DB_PATH}")


if __name__ == "__main__":
    asyncio.run(_main())
