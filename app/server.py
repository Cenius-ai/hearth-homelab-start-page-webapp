"""Hearth application entrypoint.

Run with:  python -m app.server      (preferred)
       or:  python app/server.py     (works too - the package is resolved first)

Binds 0.0.0.0 on $PORT (or $APP_PORT, default 8000) in a single process.
"""

from __future__ import annotations

# Allow `python app/server.py` as well as `python -m app.server`: when this file
# is executed as a script there is no parent package, so give the module one and
# make the project root importable before the relative imports below run.
if __package__ in (None, ""):
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    __package__ = "app"
    del _os, _sys

import asyncio
import logging
from urllib.parse import quote, urlsplit

from sanic import Request, Sanic
from sanic.exceptions import SanicException
from sanic.response import json, redirect

from . import auth, config, probe, repository as repo, seed
from .db import init_db, open_db, query_one
from .errors import ApiProblem
from .routes import auth_routes, bookmarks, bootstrap, checks, health, layout, pages, services
from .templating import render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s")
logger = logging.getLogger("hearth")

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

app = Sanic("hearth", configure_logging=False)
app.config.FALLBACK_ERROR_FORMAT = "json"
app.config.REQUEST_TIMEOUT = 30
app.config.RESPONSE_TIMEOUT = 30

app.static("/static", str(config.BASE_DIR / "app" / "static"), name="static")


# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
auth.register(app)


@app.on_request
async def cross_site_guard(request: Request):
    """SameSite=Lax already blocks cross-site cookie sends; this is the belt.

    Mutating API calls must be same-origin JSON, which a cross-site HTML form
    cannot produce.
    """
    if request.method in MUTATING_METHODS and request.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.host:
            raise ApiProblem(403, "cross_origin_blocked", message="Cross-origin request blocked.")
        # A cross-site HTML form can only send a form-encoded body, so requiring
        # JSON for any body-carrying API write means such a request can never be
        # replayed from another origin. Body-less calls (a bare recheck POST, a
        # DELETE) carry no payload to forge and are allowed.
        content_type = (request.headers.get("content-type") or "").lower()
        if (
            request.method in {"POST", "PUT", "PATCH"}
            and request.body
            and not content_type.startswith("application/json")
        ):
            raise ApiProblem(
                415, "json_required", message="Send a JSON body with Content-Type: application/json."
            )
    return None


@app.on_response
async def security_headers(request: Request, response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
@app.exception(auth.AuthRequired)
async def handle_auth_required(request: Request, error: auth.AuthRequired):
    if request.path.startswith("/api/"):
        message = (
            "Your session has expired. Please sign in again."
            if getattr(request.ctx, "expired_cookie", False)
            else "Please sign in to continue."
        )
        response = json({"error": "authentication_required", "message": message}, status=401)
        auth.clear_session_cookie(response)
        return response
    target = "/login"
    if request.method == "GET" and request.path not in ("/", "/login", "/register"):
        target = f"/login?next={quote(request.path)}"
    return redirect(target)


@app.exception(ApiProblem)
async def handle_api_problem(request: Request, error: ApiProblem):
    return json(error.payload(), status=error.status)


@app.exception(SanicException)
async def handle_sanic_exception(request: Request, error: SanicException):
    status = getattr(error, "status_code", 500) or 500
    message = getattr(error, "message", "") or ""
    if request.path.startswith("/api/"):
        return json({"error": "request_failed", "message": message or "Request failed."}, status=status)
    if status == 404:
        return render(request, "not_found.html", status=404, page_title="Page not found — Hearth Homelab Start Page")
    return render(
        request,
        "error.html",
        status=status,
        page_title="Something went wrong — Hearth Homelab Start Page",
        status_code=status,
        message=message,
    )


@app.exception(Exception)
async def handle_unexpected(request: Request, error: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.path)
    if request.path.startswith("/api/"):
        return json({"error": "internal_server_error"}, status=500)
    return render(
        request,
        "error.html",
        status=500,
        page_title="Something went wrong — Hearth Homelab Start Page",
        status_code=500,
        message="",
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
app.blueprint(
    [
        health.bp,
        auth_routes.bp,
        pages.bp,
        bootstrap.bp,
        services.bp,
        checks.bp,
        bookmarks.bp,
        layout.bp,
    ]
)


# --------------------------------------------------------------------------- #
# Boot
# --------------------------------------------------------------------------- #
async def _probe_self_task() -> None:
    """One honest health check of the seeded self-probe tile after boot."""
    await asyncio.sleep(0.75)  # let the listener accept connections first
    async with open_db() as db:
        row = await query_one(
            db, "SELECT id, url FROM services WHERE name = ?", (config.SELF_PROBE_SERVICE_NAME,)
        )
        if row is None:
            return
        result = await probe.probe(row["url"])
        await repo.record_health_check(
            db,
            row["id"],
            status=result["status"],
            latency_ms=result["latency_ms"],
            message=result["message"],
        )
    logger.info("Self-probe %s -> %s (%s ms)", row["url"], result["status"], result["latency_ms"])


@app.before_server_start
async def prepare_storage(application, loop):
    await init_db()
    async with open_db() as db:
        summary = await seed.seed_database(db)
    logger.info("Hearth database ready at %s (%s)", config.DB_PATH, summary)
    print(f"Demo login: {config.DEMO_EMAIL} / {config.DEMO_PASSWORD}", flush=True)


@app.after_server_start
async def start_probe(application, loop):
    if config.BOOT_PROBE_ENABLED:
        application.add_task(_probe_self_task())


def main() -> None:
    logger.info(
        "Hearth listening on http://%s:%s (local: %s)",
        config.HOST,
        config.PORT,
        config.local_origin(),
    )
    app.run(host=config.HOST, port=config.PORT, single_process=True, access_log=False)


if __name__ == "__main__":
    main()
