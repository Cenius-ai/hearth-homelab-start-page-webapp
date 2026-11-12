"""Runtime configuration, read from the environment with working defaults.

Nothing here is required: a fresh clone boots with no environment variables and
no .env file. `.env` is read when present (without overriding real env vars) so
that copying `.env.example` to `.env` behaves the way the README says it does.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_VERSION = "0.1.0"


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a KEY=VALUE file, never overriding the real env."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


def _env_text(name: str, default: str) -> str:
    """Environment value, falling back to `default` when unset *or* empty.

    Empty matters: `cp .env.example .env` writes `NAME=` lines, and a dotted
    empty value must mean "not configured", never "configured to nothing".
    """
    value = (os.getenv(name) or "").strip()
    return value or default


def _positive_int(raw: str | None, fallback: int) -> int:
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


# `PORT` is what containers and PaaS runners inject; `APP_PORT` is Hearth's own
# documented knob. Both fall back to Sanic's conventional 8000.
PORT = _positive_int(os.getenv("PORT") or os.getenv("APP_PORT"), 8000)
HOST = os.getenv("APP_HOST") or "0.0.0.0"

_data_dir = os.getenv("DATA_DIR") or str(BASE_DIR / "data")
DATA_DIR = Path(_data_dir).expanduser()
if not DATA_DIR.is_absolute():
    DATA_DIR = (BASE_DIR / DATA_DIR).resolve()
DB_PATH = Path(os.getenv("HEARTH_DB_PATH") or (DATA_DIR / "hearth.db"))

SESSION_TTL_DAYS = _positive_int(os.getenv("SESSION_TTL_DAYS"), 30)
SESSION_COOKIE = os.getenv("SESSION_COOKIE_NAME") or "hearth_session"

# Login throttling (per client address, and per account). Generous for a
# household on a LAN; tightened at the edge if the app is ever exposed.
LOGIN_IP_LIMIT = _positive_int(os.getenv("HEARTH_LOGIN_IP_LIMIT"), 10)
LOGIN_ACCOUNT_LIMIT = _positive_int(os.getenv("HEARTH_LOGIN_ACCOUNT_LIMIT"), 8)

# Health probes are capped so a dead LAN host can never hang a request.
PROBE_TIMEOUT_SECONDS = 2.5
BOOT_PROBE_ENABLED = os.getenv("HEARTH_BOOT_PROBE", "1") != "0"

# Seeded demo accounts.
#
# These read from the environment and fall back to documented, non-production
# defaults so a fresh clone demonstrates itself and the login card can show what
# to type. They are deliberately public credentials for a local-only demo box -
# set the HEARTH_DEMO_* variables (or delete the accounts) before exposing
# Hearth to anything but your own LAN. Nothing here is required to boot.
DEMO_EMAIL = _env_text("HEARTH_DEMO_EMAIL", "cenius@cenius.ai").lower()
DEMO_PASSWORD = _env_text("HEARTH_DEMO_PASSWORD", "cenius")
SECOND_DEMO_EMAIL = _env_text("HEARTH_SECOND_DEMO_EMAIL", "demo@hearth.local").lower()
SECOND_DEMO_PASSWORD = _env_text("HEARTH_SECOND_DEMO_PASSWORD", "hearth-demo")

SELF_PROBE_SERVICE_NAME = "Hearth (this page)"

# Where this process reaches itself. The seeded self-probe tile and the startup
# log use it. The host is env-overridable so the same build works on a laptop
# (loopback), on a LAN host, or behind a reverse proxy where loopback is not the
# right address; nothing here is required to boot.
PROBE_HOST = _env_text("HEARTH_PROBE_HOST", "127.0.0.1")
BASE_URL = (os.getenv("HEARTH_BASE_URL") or "").strip().rstrip("/")


def local_origin() -> str:
    """The origin this process serves on, as seen from the same machine."""
    return BASE_URL or f"http://{PROBE_HOST}:{PORT}"


def self_probe_url() -> str:
    """Full URL of the liveness route the seeded self-probe tile checks."""
    override = (os.getenv("HEARTH_SELF_PROBE_URL") or "").strip()
    return override or f"{local_origin()}/healthz"
