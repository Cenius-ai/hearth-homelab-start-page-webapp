"""Session handling.

Every authenticated request resolves the `hearth_session` cookie to a row in
`sessions`. A row whose `expires_at` is in the past is deleted on sight and the
caller is treated as signed out - there is no other code path that accepts a
cookie without this check.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sanic import Request

from . import config
from .db import execute, insert, query_one
from .formatting import iso, parse_iso, utcnow
from .security import hash_session_token, new_session_token


class AuthRequired(Exception):
    """Raised by a handler that needs a signed-in user and found none."""


async def create_session(db, user_id: int) -> tuple[str, str]:
    """Create a session row and return (cookie_token, expires_at_iso)."""
    token = new_session_token()
    now = utcnow()
    expires_at = iso(now + timedelta(days=config.SESSION_TTL_DAYS))
    await insert(
        db,
        "INSERT INTO sessions (user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user_id, hash_session_token(token), expires_at, iso(now)),
    )
    return token, expires_at


async def resolve_session(db, token: str) -> tuple[dict[str, Any] | None, bool]:
    """Return (user, was_expired).

    `was_expired` is True when a cookie existed but its row is past its expiry:
    the row is deleted here and the response clears the cookie.
    """
    row = await query_one(
        db,
        "SELECT s.id AS session_id, s.expires_at, u.id AS user_id, u.email "
        "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
        (hash_session_token(token),),
    )
    if row is None:
        return None, False

    expires_at = parse_iso(row["expires_at"])
    if expires_at is None or expires_at <= utcnow():
        await execute(db, "DELETE FROM sessions WHERE id = ?", (row["session_id"],))
        return None, True

    return {"id": row["user_id"], "email": row["email"]}, False


async def destroy_session(db, token: str) -> None:
    await execute(db, "DELETE FROM sessions WHERE token_hash = ?", (hash_session_token(token),))


def current_user(request: Request) -> dict[str, Any] | None:
    return getattr(request.ctx, "user", None)


def require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if user is None:
        raise AuthRequired()
    return user


def set_session_cookie(response, token: str) -> None:
    response.add_cookie(
        config.SESSION_COOKIE,
        token,
        path="/",
        max_age=config.SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="Lax",
        secure=False,  # The app is documented to run behind plain HTTP on a LAN.
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(config.SESSION_COOKIE, path="/")


def register(app) -> None:
    """Install the request/response middleware that resolves the session."""

    @app.on_request
    async def load_session(request: Request):
        from .db import open_db  # local import keeps module import order simple

        request.ctx.user = None
        request.ctx.expired_cookie = False
        token = request.cookies.get(config.SESSION_COOKIE)
        if not token:
            return None
        async with open_db() as db:
            user, was_expired = await resolve_session(db, token)
        request.ctx.user = user
        request.ctx.expired_cookie = was_expired
        return None

    @app.on_response
    async def clear_expired_cookie(request: Request, response):
        if getattr(request.ctx, "expired_cookie", False):
            clear_session_cookie(response)
        return response
