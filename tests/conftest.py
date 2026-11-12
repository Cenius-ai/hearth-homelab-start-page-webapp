"""Test bootstrap: point the app at a throwaway database before importing it."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Config reads the environment at import time, so this must happen first.
_TMP_DIR = tempfile.mkdtemp(prefix="hearth-tests-")
os.environ["DATA_DIR"] = _TMP_DIR
os.environ["HEARTH_DB_PATH"] = str(Path(_TMP_DIR) / "hearth.db")
os.environ["HEARTH_BOOT_PROBE"] = "0"
# The suite signs in dozens of times from one address; keep the production
# throttle out of the way and cover the limiter itself with a unit test.
os.environ["HEARTH_LOGIN_IP_LIMIT"] = "10000"
os.environ["HEARTH_LOGIN_ACCOUNT_LIMIT"] = "10000"
os.environ.pop("PORT", None)

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.server import app  # noqa: E402


class TestSession:
    """Thin wrapper over Sanic's test client: it returns (request, response)."""

    def __init__(self, client) -> None:
        self._client = client

    def _call(self, method: str, uri: str, **kwargs):
        result = getattr(self._client, method)(uri, **kwargs)
        return result[1] if isinstance(result, tuple) else result

    def get(self, uri, **kwargs):
        return self._call("get", uri, **kwargs)

    def post(self, uri, **kwargs):
        return self._call("post", uri, **kwargs)

    def put(self, uri, **kwargs):
        return self._call("put", uri, **kwargs)

    def patch(self, uri, **kwargs):
        return self._call("patch", uri, **kwargs)

    def delete(self, uri, **kwargs):
        return self._call("delete", uri, **kwargs)


@pytest.fixture(scope="session")
def client():
    """Sanic's own test client: each call boots the real server on a free port."""
    return TestSession(app.test_client)


@pytest.fixture(scope="session")
def db_path() -> Path:
    return Path(config.DB_PATH)


def login(client, email: str | None = None, password: str | None = None) -> dict[str, str]:
    """Sign in and return the cookie dict the API expects."""
    email = email or config.DEMO_EMAIL
    password = password or config.DEMO_PASSWORD
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status == 200, response.text
    token = response.cookies.get(config.SESSION_COOKIE)
    assert token, "login did not issue a session cookie"
    return {config.SESSION_COOKIE: token}


def ensure_user(client, email: str, password: str) -> dict[str, str]:
    """Sign in if the account exists, otherwise register it."""
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    if response.status == 200:
        return login(client, email, password)
    created = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "confirm_password": password},
    )
    assert created.status in (201, 422), created.text
    return login(client, email, password)
