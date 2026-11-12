"""End-to-end tests for Hearth.

Every test drives the real Sanic app (the boot path, the real SQLite file, the
real auth flow) through Sanic's own test client.
"""

from __future__ import annotations

import http.server
import socket
import sqlite3
import threading

import pytest

from app import config, formatting, ordering, probe, security, seed
from app.validate import host_port
from tests.conftest import ensure_user, login

SERVICE_PAYLOAD = {
    "name": "Plex",
    "url": "http://192.168.1.20:32400",
    "category_id": 1,
    "icon": "🎬",
}


def create_service(client, cookies, **overrides):
    payload = dict(SERVICE_PAYLOAD)
    payload.update(overrides)
    return client.post("/api/services", json=payload, cookies=cookies)


def delete_service(client, cookies, service_id):
    response = client.delete(f"/api/services/{service_id}", cookies=cookies)
    assert response.status == 204, response.text


def service_names(payload):
    return [service["name"] for service in payload["services"]]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# --------------------------------------------------------------------------- #
# Boot, liveness and auth gate
# --------------------------------------------------------------------------- #
def test_healthz_is_public_and_reports_version(client):
    response = client.get("/healthz")
    assert response.status == 200
    body = response.json
    assert body["status"] == "ok"
    assert body["app"] == "hearth"
    assert body["version"] == config.APP_VERSION
    assert formatting.parse_iso(body["time"]) is not None


def test_root_redirects_signed_out_visitors_to_login(client):
    response = client.get("/", allow_redirects=False)
    assert response.status == 302
    assert response.headers["location"].startswith("/login")


def test_login_page_prints_the_demo_credentials(client):
    response = client.get("/login")
    assert response.status == 200
    assert f"Demo: {config.DEMO_EMAIL} / {config.DEMO_PASSWORD}" in response.text
    assert 'type="password"' in response.text
    assert 'id="password-toggle"' in response.text


def test_login_issues_an_httponly_session_cookie(client):
    response = client.post(
        "/api/auth/login",
        json={"email": config.DEMO_EMAIL, "password": config.DEMO_PASSWORD},
    )
    assert response.status == 200
    assert response.json["user"]["email"] == config.DEMO_EMAIL
    set_cookie = response.headers.get("set-cookie", "")
    assert config.SESSION_COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie


def test_login_rejects_bad_credentials_without_revealing_which(client):
    wrong_password = client.post(
        "/api/auth/login", json={"email": config.DEMO_EMAIL, "password": "nope-nope"}
    )
    unknown_email = client.post(
        "/api/auth/login", json={"email": "ghost@hearth.local", "password": "nope-nope"}
    )
    assert wrong_password.status == 401
    assert unknown_email.status == 401
    assert wrong_password.json["message"] == unknown_email.json["message"]
    assert wrong_password.json["message"] == "Email or password is incorrect"
    assert "set-cookie" not in {key.lower() for key in unknown_email.headers}


def test_login_validates_fields_server_side(client):
    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": ""})
    assert response.status == 422
    errors = response.json["errors"]
    assert "email" in errors and "password" in errors


def test_expired_session_is_deleted_and_rejected(client, db_path):
    cookies = login(client)
    token = cookies[config.SESSION_COOKIE]

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
            ("2020-01-01T00:00:00+00:00", security.hash_session_token(token)),
        )
        connection.commit()

    response = client.get("/api/bootstrap", cookies=cookies)
    assert response.status == 401
    assert response.json["error"] == "authentication_required"
    assert config.SESSION_COOKIE in response.headers.get("set-cookie", "")

    with sqlite3.connect(db_path) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE token_hash = ?",
            (security.hash_session_token(token),),
        ).fetchone()[0]
    assert remaining == 0


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def test_register_creates_account_signs_in_and_starts_empty(client):
    email = "household-register@hearth.test"
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "kitchen-table", "confirm_password": "kitchen-table"},
    )
    assert response.status == 201, response.text
    cookies = {config.SESSION_COOKIE: response.cookies.get(config.SESSION_COOKIE)}

    payload = client.get("/api/bootstrap", cookies=cookies).json
    assert payload["bookmarks"] == []
    # A brand-new account sees the shared catalog in default order.
    assert service_names(payload)[0] == "Jellyfin"


def test_register_rejects_duplicate_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": config.DEMO_EMAIL.upper(),
            "password": "***REDACTED-SECRET***",
            "confirm_password": "***REDACTED-SECRET***",
        },
    )
    assert response.status == 422
    assert "already registered" in response.json["errors"]["email"]


def test_register_rejects_short_password_and_mismatch(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@hearth.test", "password": "short", "confirm_password": "shorter"},
    )
    assert response.status == 422
    errors = response.json["errors"]
    assert "password" in errors


# --------------------------------------------------------------------------- #
# Bootstrap payload, ordering and host:port derivation
# --------------------------------------------------------------------------- #
def test_bootstrap_payload_shape(client):
    cookies = login(client)
    response = client.get("/api/bootstrap", cookies=cookies)
    assert response.status == 200
    payload = response.json

    assert payload["user"]["email"] == config.DEMO_EMAIL
    assert [group["name"] for group in payload["groups"]] == [
        "Media",
        "Network",
        "Infrastructure",
        "Observability",
    ]
    assert all(group["services"] for group in payload["groups"])

    jellyfin = payload["services"][0]
    assert jellyfin["host_port"] == "jellyfin.lan:8096"
    assert jellyfin["health"]["status"] in {"up", "down"}
    assert len(payload["bookmarks"]) >= 4
    assert "layout" in payload


def test_host_port_derivation_uses_scheme_defaults():
    assert host_port("https://media.local:8096") == ("media.local", 8096)
    assert host_port("https://cloud.example.com") == ("cloud.example.com", 443)
    assert host_port("http://192.168.1.1") == ("192.168.1.1", 80)


def test_order_services_appends_unpositioned_tiles():
    services = [
        {"id": 1, "sort_order": 0},
        {"id": 2, "sort_order": 1},
        {"id": 3, "sort_order": 2},
        {"id": 4, "sort_order": 3},
    ]
    ordered = ordering.order_services(services, {3: 0, 1: 1})
    assert [service["id"] for service in ordered] == [3, 1, 2, 4]


# --------------------------------------------------------------------------- #
# Service CRUD
# --------------------------------------------------------------------------- #
def test_create_service_appears_in_bootstrap_and_bumps_host_port(client):
    cookies = login(client)
    created = create_service(client, cookies, name="Audiobookshelf", url="https://books.lan:13378")
    assert created.status == 201, created.text
    service = created.json["service"]
    assert service["host_port"] == "books.lan:13378"

    payload = client.get("/api/bootstrap", cookies=cookies).json
    assert "Audiobookshelf" in service_names(payload)

    delete_service(client, cookies, service["id"])
    payload = client.get("/api/bootstrap", cookies=cookies).json
    assert "Audiobookshelf" not in service_names(payload)


def test_create_service_rejects_malformed_url(client):
    cookies = login(client)
    before = len(client.get("/api/bootstrap", cookies=cookies).json["services"])

    response = create_service(client, cookies, url="not a url")
    assert response.status == 422
    assert "url" in response.json["errors"]

    after = len(client.get("/api/bootstrap", cookies=cookies).json["services"])
    assert after == before


def test_create_service_rejects_unknown_category(client):
    cookies = login(client)
    response = create_service(client, cookies, category_id=9999)
    assert response.status == 422
    assert "category_id" in response.json["errors"]


def test_update_service_changes_name_and_url(client):
    cookies = login(client)
    service = create_service(client, cookies, name="Old Name").json["service"]

    response = client.patch(
        f"/api/services/{service['id']}",
        json={"name": "New Name", "url": "https://renamed.lan:8443"},
        cookies=cookies,
    )
    assert response.status == 200
    assert response.json["service"]["name"] == "New Name"
    assert response.json["service"]["host_port"] == "renamed.lan:8443"

    delete_service(client, cookies, service["id"])


def test_deleting_a_service_cascades_health_checks_and_layout(client, db_path):
    cookies = login(client)
    service = create_service(client, cookies).json["service"]
    service_id = service["id"]

    payload = client.get("/api/bootstrap", cookies=cookies).json
    order = [item["id"] for item in payload["services"] if item["id"] != service_id]
    order.insert(0, service_id)
    assert client.put("/api/layout", json={"service_ids": order}, cookies=cookies).status == 200

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO health_checks (service_id, status, latency_ms, message, checked_at) "
            "VALUES (?, 'up', 12, 'HTTP 200', '2024-01-01T00:00:00+00:00')",
            (service_id,),
        )
        connection.commit()

    delete_service(client, cookies, service_id)

    with sqlite3.connect(db_path) as connection:
        checks = connection.execute(
            "SELECT COUNT(*) FROM health_checks WHERE service_id = ?", (service_id,)
        ).fetchone()[0]
        layout = connection.execute(
            "SELECT COUNT(*) FROM layout_items WHERE service_id = ?", (service_id,)
        ).fetchone()[0]
    assert checks == 0
    assert layout == 0


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
def test_layout_save_is_per_user_and_survives_reload(client):
    cookies_a = login(client)
    cookies_b = ensure_user(client, "household-layout@hearth.test", "layout-password")

    payload = client.get("/api/bootstrap", cookies=cookies_a).json
    reversed_ids = [item["id"] for item in payload["services"]][::-1]

    saved = client.put("/api/layout", json={"service_ids": reversed_ids}, cookies=cookies_a)
    assert saved.status == 200

    reloaded = client.get("/api/bootstrap", cookies=cookies_a).json
    assert [item["id"] for item in reloaded["services"]] == reversed_ids
    assert reloaded["has_custom_layout"] is True

    other_user = client.get("/api/bootstrap", cookies=cookies_b).json
    assert [item["id"] for item in other_user["services"]] != reversed_ids
    assert other_user["has_custom_layout"] is False
    assert service_names(other_user)[0] == "Jellyfin"


def test_layout_rejects_unknown_service_and_keeps_previous_order(client):
    cookies = login(client)
    payload = client.get("/api/bootstrap", cookies=cookies).json
    good_order = [item["id"] for item in payload["services"]]
    client.put("/api/layout", json={"service_ids": good_order}, cookies=cookies)

    response = client.put(
        "/api/layout", json={"service_ids": [999999] + good_order}, cookies=cookies
    )
    assert response.status == 422
    assert "service_ids" in response.json["errors"]

    unchanged = client.get("/api/bootstrap", cookies=cookies).json
    assert [item["id"] for item in unchanged["services"]] == good_order


def test_new_service_appears_last_after_a_custom_layout(client):
    cookies = login(client)
    payload = client.get("/api/bootstrap", cookies=cookies).json
    client.put(
        "/api/layout", json={"service_ids": [item["id"] for item in payload["services"]]}, cookies=cookies
    )

    created = create_service(client, cookies, name="Latecomer", url="http://late.lan:8080").json["service"]
    payload = client.get("/api/bootstrap", cookies=cookies).json
    assert payload["services"][-1]["id"] == created["id"]

    delete_service(client, cookies, created["id"])


# --------------------------------------------------------------------------- #
# Health checks
# --------------------------------------------------------------------------- #
class _OKHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib callback name
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the test output clean
        return


@pytest.fixture()
def local_http_server():
    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _OKHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_recheck_records_a_real_probe(client, db_path, local_http_server):
    cookies = login(client)
    service = create_service(
        client, cookies, name="Live probe", url=f"http://127.0.0.1:{local_http_server}/"
    ).json["service"]

    response = client.post(f"/api/services/{service['id']}/check", cookies=cookies)
    assert response.status == 200, response.text
    health = response.json["health"]
    assert health["status"] == "up"
    assert health["latency_ms"] is not None

    payload = client.get("/api/bootstrap", cookies=cookies).json
    probe_tile = next(item for item in payload["services"] if item["id"] == service["id"])
    assert probe_tile["health"]["status"] == "up"

    with sqlite3.connect(db_path) as connection:
        stored = connection.execute(
            "SELECT COUNT(*) FROM health_checks WHERE service_id = ?", (service["id"],)
        ).fetchone()[0]
    assert stored == 1

    delete_service(client, cookies, service["id"])


def test_recheck_of_dead_host_records_down_quickly(client):
    cookies = login(client)
    dead_port = free_port()  # nothing is listening on it
    service = create_service(
        client, cookies, name="Dead probe", url=f"http://127.0.0.1:{dead_port}/"
    ).json["service"]

    response = client.post(f"/api/services/{service['id']}/check", cookies=cookies)
    assert response.status == 200
    assert response.json["health"]["status"] == "down"

    delete_service(client, cookies, service["id"])


def test_probe_reports_timeout_for_unroutable_address():
    result = probe.probe_url_sync("http://10.255.255.1:9/", timeout=0.4)
    assert result[0] == "down"
    assert result[2] in {"timeout", "unreachable"} or result[2]


def test_check_unknown_service_is_404(client):
    cookies = login(client)
    response = client.post("/api/services/999999/check", cookies=cookies)
    assert response.status == 404


# --------------------------------------------------------------------------- #
# Bookmarks
# --------------------------------------------------------------------------- #
def test_bookmarks_are_scoped_to_the_owner(client):
    cookies_a = login(client)
    cookies_b = ensure_user(client, "household-books@hearth.test", "bookmark-password")

    created = client.post(
        "/api/bookmarks",
        json={"label": "Proxmox", "url": "https://proxmox.local:8006"},
        cookies=cookies_a,
    )
    assert created.status == 201, created.text
    bookmark_id = created.json["bookmark"]["id"]

    labels_a = [item["label"] for item in client.get("/api/bootstrap", cookies=cookies_a).json["bookmarks"]]
    labels_b = [item["label"] for item in client.get("/api/bootstrap", cookies=cookies_b).json["bookmarks"]]
    assert "Proxmox" in labels_a
    assert "Proxmox" not in labels_b

    # User B cannot delete user A's bookmark, and gets the same answer as "missing".
    stolen = client.delete(f"/api/bookmarks/{bookmark_id}", cookies=cookies_b)
    assert stolen.status == 404
    labels_a = [item["label"] for item in client.get("/api/bootstrap", cookies=cookies_a).json["bookmarks"]]
    assert "Proxmox" in labels_a

    assert client.delete(f"/api/bookmarks/{bookmark_id}", cookies=cookies_a).status == 204


def test_bookmark_rejects_javascript_scheme(client):
    cookies = login(client)
    response = client.post(
        "/api/bookmarks", json={"label": "Evil", "url": "javascript:alert(1)"}, cookies=cookies
    )
    assert response.status == 422
    assert "url" in response.json["errors"]


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def test_signed_in_pages_render_real_content(client):
    cookies = login(client)
    dashboard = client.get("/", cookies=cookies)
    assert dashboard.status == 200
    assert "Start page" in dashboard.text
    assert "jellyfin.lan:8096" in dashboard.text
    assert 'class="tile"' in dashboard.text

    services_page = client.get("/services", cookies=cookies)
    assert services_page.status == 200
    assert "All services" in services_page.text
    assert "Navidrome" in services_page.text

    new_page = client.get("/services/new", cookies=cookies)
    assert new_page.status == 200
    assert 'action="/services/new"' in new_page.text

    detail = client.get("/services/1", cookies=cookies)
    assert detail.status == 200
    assert "Check history" in detail.text

    edit_page = client.get("/services/1/edit", cookies=cookies)
    assert edit_page.status == 200
    assert 'value="Jellyfin"' in edit_page.text

    activity = client.get("/activity", cookies=cookies)
    assert activity.status == 200
    assert "Check log" in activity.text


def test_plain_form_create_redirects_to_the_new_service(client):
    cookies = login(client)
    response = client.post(
        "/services/new",
        data={"name": "Form Post", "url": "http://form.lan:8081", "category_id": "2", "icon": "📝"},
        cookies=cookies,
        allow_redirects=False,
    )
    assert response.status == 303
    location = response.headers["location"]
    assert location.startswith("/services/")

    detail = client.get(location, cookies=cookies)
    assert detail.status == 200
    assert "Form Post" in detail.text

    service_id = int(location.rsplit("/", 1)[-1])
    delete_service(client, cookies, service_id)


def test_plain_form_create_keeps_values_and_reports_errors(client):
    cookies = login(client)
    response = client.post(
        "/services/new",
        data={"name": "", "url": "ftp:/broken", "category_id": "1"},
        cookies=cookies,
        allow_redirects=False,
    )
    assert response.status == 422
    assert "Please give the service a name." in response.text
    assert "URL must start with http:// or https://" in response.text
    assert 'value="ftp:/broken"' in response.text


def test_unknown_page_returns_the_404_screen(client):
    response = client.get("/does-not-exist", allow_redirects=False)
    assert response.status == 404
    assert "That page isn’t in the house" in response.text


def test_security_headers_are_present(client):
    response = client.get("/login")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


# --------------------------------------------------------------------------- #
# Storage-level guarantees
# --------------------------------------------------------------------------- #
def test_password_hash_verifies_and_is_salted():
    password_hash, salt = security.hash_password("hearth-demo")
    assert security.verify_password("hearth-demo", salt, password_hash)
    assert not security.verify_password("hearth-dem0", salt, password_hash)

    other_hash, other_salt = security.hash_password("hearth-demo")
    assert other_salt != salt
    assert other_hash != password_hash


def test_search_of_seeded_users_verifies_the_demo_password(client, db_path):
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT password_hash, salt FROM users WHERE email = ?", (config.DEMO_EMAIL,)
        ).fetchone()
    assert row is not None
    assert security.verify_password(config.DEMO_PASSWORD, row[1], row[0])


def test_seed_is_idempotent(client, db_path):
    """The app re-seeds on every boot; running it again must change nothing."""

    async def run_seed_again():
        await seed.run_seed()

    import asyncio

    def counts():
        with sqlite3.connect(db_path) as connection:
            return tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("users", "categories", "services", "bookmarks")
            )

    before = counts()
    asyncio.run(run_seed_again())
    asyncio.run(run_seed_again())
    assert counts() == before


def test_deleting_a_user_cascades_sessions_layout_and_bookmarks(client, db_path):
    cookies = ensure_user(client, "household-cascade@hearth.test", "cascade-password")
    payload = client.get("/api/bootstrap", cookies=cookies).json
    client.put(
        "/api/layout", json={"service_ids": [item["id"] for item in payload["services"]]}, cookies=cookies
    )
    client.post("/api/bookmarks", json={"label": "Cascade", "url": "http://cascade.lan/"}, cookies=cookies)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        user_id = connection.execute(
            "SELECT id FROM users WHERE email = ?", ("household-cascade@hearth.test",)
        ).fetchone()[0]
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()

        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM layout_items WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            == 0
        )


# --------------------------------------------------------------------------- #
# Abuse controls
# --------------------------------------------------------------------------- #
def test_login_rate_limiter_blocks_after_the_window_limit():
    from app.ratelimit import SlidingWindowLimiter

    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False
    # A different client keeps its own budget.
    assert limiter.allow("5.6.7.8") is True
