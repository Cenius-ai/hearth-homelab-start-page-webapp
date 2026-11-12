"""All SQL lives here.

Route handlers stay thin: they validate input, resolve the signed-in user and
call one of these functions. Every statement is parameterised; the only
interpolated SQL is a fixed column list defined in this module.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import aiosqlite

from .db import execute, insert, query_all, query_one
from .formatting import iso, utcnow
from .ordering import group_by_category, order_services
from .validate import FALLBACK_ICON, host_port

SERVICE_COLUMNS = "id, name, url, category_id, icon, sort_order, created_at, updated_at"

_LATEST_HEALTH_SQL = """
    SELECT service_id, status, latency_ms, message, checked_at
    FROM (
        SELECT service_id, status, latency_ms, message, checked_at,
               ROW_NUMBER() OVER (
                   PARTITION BY service_id ORDER BY checked_at DESC, id DESC
               ) AS row_number
        FROM health_checks
    )
    WHERE row_number = 1
"""


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
async def list_categories(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    rows = await query_all(db, "SELECT id, name, sort_order FROM categories ORDER BY sort_order, id")
    return [dict(row) for row in rows]


async def category_exists(db: aiosqlite.Connection, category_id: int) -> bool:
    row = await query_one(db, "SELECT 1 FROM categories WHERE id = ?", (category_id,))
    return row is not None


async def list_services(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    rows = await query_all(db, f"SELECT {SERVICE_COLUMNS} FROM services ORDER BY sort_order, id")
    return [dict(row) for row in rows]


async def get_service(db: aiosqlite.Connection, service_id: int) -> dict[str, Any] | None:
    row = await query_one(db, f"SELECT {SERVICE_COLUMNS} FROM services WHERE id = ?", (service_id,))
    return dict(row) if row else None


async def latest_health(db: aiosqlite.Connection) -> dict[int, dict[str, Any]]:
    rows = await query_all(db, _LATEST_HEALTH_SQL)
    return {row["service_id"]: dict(row) for row in rows}


async def latest_health_for(db: aiosqlite.Connection, service_id: int) -> dict[str, Any] | None:
    row = await query_one(
        db,
        "SELECT service_id, status, latency_ms, message, checked_at "
        "FROM health_checks WHERE service_id = ? ORDER BY checked_at DESC, id DESC LIMIT 1",
        (service_id,),
    )
    return dict(row) if row else None


async def check_history(db: aiosqlite.Connection, service_id: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = await query_all(
        db,
        "SELECT id, status, latency_ms, message, checked_at FROM health_checks "
        "WHERE service_id = ? ORDER BY checked_at DESC, id DESC LIMIT ?",
        (service_id, limit),
    )
    return [dict(row) for row in rows]


async def recent_checks(db: aiosqlite.Connection, limit: int = 60) -> list[dict[str, Any]]:
    rows = await query_all(
        db,
        "SELECT h.id, h.status, h.latency_ms, h.message, h.checked_at, "
        "       s.id AS service_id, s.name AS service_name, s.icon AS service_icon, "
        "       c.name AS category_name "
        "FROM health_checks h "
        "JOIN services s ON s.id = h.service_id "
        "JOIN categories c ON c.id = s.category_id "
        "ORDER BY h.checked_at DESC, h.id DESC LIMIT ?",
        (limit,),
    )
    return [dict(row) for row in rows]


async def layout_positions(db: aiosqlite.Connection, user_id: int) -> dict[int, int]:
    rows = await query_all(db, "SELECT service_id, position FROM layout_items WHERE user_id = ?", (user_id,))
    return {row["service_id"]: row["position"] for row in rows}


async def list_bookmarks(db: aiosqlite.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = await query_all(
        db,
        "SELECT id, label, url, sort_order, created_at FROM bookmarks "
        "WHERE user_id = ? ORDER BY sort_order, id",
        (user_id,),
    )
    return [dict(row) for row in rows]


async def get_bookmark(db: aiosqlite.Connection, user_id: int, bookmark_id: int) -> dict[str, Any] | None:
    row = await query_one(
        db,
        "SELECT id, label, url, sort_order, created_at FROM bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, user_id),
    )
    return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def service_payload(service: dict[str, Any], health: dict[str, Any] | None) -> dict[str, Any]:
    host, port = host_port(service["url"])
    return {
        "id": service["id"],
        "name": service["name"],
        "url": service["url"],
        "category_id": service["category_id"],
        "icon": service["icon"] or FALLBACK_ICON,
        "sort_order": service["sort_order"],
        "host": host,
        "port": port,
        "host_port": f"{host}:{port}",
        "health": health,
        "created_at": service["created_at"],
        "updated_at": service["updated_at"],
    }


async def build_dashboard(db: aiosqlite.Connection, user: dict[str, Any]) -> dict[str, Any]:
    """The single payload behind both the dashboard page and /api/bootstrap."""
    categories = await list_categories(db)
    services = await list_services(db)
    health = await latest_health(db)
    positions = await layout_positions(db, user["id"])
    bookmarks = await list_bookmarks(db, user["id"])

    ordered = order_services(services, positions)
    payload_services = [service_payload(service, health.get(service["id"])) for service in ordered]
    groups = group_by_category(categories, payload_services)

    return {
        "user": {"id": user["id"], "email": user["email"]},
        "groups": groups,
        "services": payload_services,
        "categories": categories,
        "bookmarks": bookmarks,
        "layout": [service["id"] for service in payload_services],
        "has_custom_layout": bool(positions),
    }


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
async def create_service(
    db: aiosqlite.Connection, *, name: str, url: str, category_id: int, icon: str
) -> dict[str, Any]:
    now = iso(utcnow())
    row = await query_one(db, "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next FROM services")
    next_order = int(row["next"]) if row else 0
    service_id = await insert(
        db,
        "INSERT INTO services (name, url, category_id, icon, sort_order, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, url, category_id, icon, next_order, now, now),
    )
    service = await get_service(db, service_id)
    assert service is not None
    return service


async def update_service(
    db: aiosqlite.Connection, service_id: int, fields: dict[str, Any]
) -> dict[str, Any] | None:
    assignments: list[str] = []
    values: list[Any] = []
    for column in ("name", "url", "category_id", "icon"):
        if column in fields:
            assignments.append(f"{column} = ?")
            values.append(fields[column])
    if not assignments:
        return await get_service(db, service_id)
    assignments.append("updated_at = ?")
    values.append(iso(utcnow()))
    values.append(service_id)
    changed = await execute(db, f"UPDATE services SET {', '.join(assignments)} WHERE id = ?", values)
    if changed == 0:
        return None
    return await get_service(db, service_id)


async def delete_service(db: aiosqlite.Connection, service_id: int) -> bool:
    changed = await execute(db, "DELETE FROM services WHERE id = ?", (service_id,))
    return changed > 0


async def record_health_check(
    db: aiosqlite.Connection, service_id: int, *, status: str, latency_ms: int | None, message: str | None
) -> dict[str, Any]:
    checked_at = iso(utcnow())
    check_id = await insert(
        db,
        "INSERT INTO health_checks (service_id, status, latency_ms, message, checked_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (service_id, status, latency_ms, message, checked_at),
    )
    return {
        "id": check_id,
        "service_id": service_id,
        "status": status,
        "latency_ms": latency_ms,
        "message": message,
        "checked_at": checked_at,
    }


async def create_bookmark(db: aiosqlite.Connection, user_id: int, *, label: str, url: str) -> dict[str, Any]:
    row = await query_one(
        db, "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next FROM bookmarks WHERE user_id = ?", (user_id,)
    )
    next_order = int(row["next"]) if row else 0
    bookmark_id = await insert(
        db,
        "INSERT INTO bookmarks (user_id, label, url, sort_order, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, label, url, next_order, iso(utcnow())),
    )
    bookmark = await get_bookmark(db, user_id, bookmark_id)
    assert bookmark is not None
    return bookmark


async def delete_bookmark(db: aiosqlite.Connection, user_id: int, bookmark_id: int) -> bool:
    changed = await execute(db, "DELETE FROM bookmarks WHERE id = ? AND user_id = ?", (bookmark_id, user_id))
    return changed > 0


async def save_layout(db: aiosqlite.Connection, user_id: int, service_ids: Sequence[int]) -> list[int]:
    """Replace this user's LayoutItem rows with the given order (positions 0..n-1)."""
    await execute(db, "DELETE FROM layout_items WHERE user_id = ?", (user_id,))
    if service_ids:
        rows = [(user_id, service_id, position) for position, service_id in enumerate(service_ids)]
        await db.executemany(
            "INSERT INTO layout_items (user_id, service_id, position) VALUES (?, ?, ?)", rows
        )
        await db.commit()
    return list(service_ids)


async def existing_service_ids(db: aiosqlite.Connection, service_ids: Iterable[int]) -> set[int]:
    ids = list(dict.fromkeys(service_ids))
    if not ids:
        return set()
    placeholders = ", ".join("?" for _ in ids)
    rows = await query_all(db, f"SELECT id FROM services WHERE id IN ({placeholders})", ids)
    return {row["id"] for row in rows}
