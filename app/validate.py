"""Server-side validation for every value a client can send.

Each validator returns a human message, or None when the value is acceptable.
The same functions back the JSON API and the plain server-rendered forms, so a
rule can never drift between the two.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
ALLOWED_SCHEMES = {"http", "https"}

MAX_NAME_LENGTH = 60
MAX_URL_LENGTH = 500
MAX_LABEL_LENGTH = 40
MIN_PASSWORD_LENGTH = 8
FALLBACK_ICON = "🔗"


def clean_text(value: object, *, limit: int) -> str:
    """Trim and hard-cap a free-text field; non-strings become empty strings."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def validate_email(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "Please enter your email address."
    address = value.strip()
    if len(address) > 254:
        return "That email address is too long."
    if not EMAIL_RE.match(address):
        return "Please enter a valid email address."
    return None


def validate_password(value: object, *, min_length: int = MIN_PASSWORD_LENGTH) -> str | None:
    if not isinstance(value, str) or not value:
        return "Please enter a password."
    if len(value) < min_length:
        return f"Password must be at least {min_length} characters."
    if len(value) > 200:
        return "That password is too long."
    return None


def validate_url(value: object) -> str | None:
    """Only absolute http/https URLs with a host are accepted."""
    if not isinstance(value, str) or not value.strip():
        return "Please enter a URL."
    url = value.strip()
    if len(url) > MAX_URL_LENGTH:
        return "That URL is too long."
    if any(character.isspace() for character in url):
        return "URLs cannot contain spaces."
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        return "URL must start with http:// or https://"
    if not parts.hostname:
        return "URL must include a host, for example http://jellyfin.lan:8096"
    try:
        parts.port  # noqa: B018 - accessing .port validates the port number
    except ValueError:
        return "That URL has an invalid port."
    return None


def validate_name(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "Please give the service a name."
    if len(value.strip()) > MAX_NAME_LENGTH:
        return f"Names are limited to {MAX_NAME_LENGTH} characters."
    return None


def validate_label(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "Please give the bookmark a label."
    if len(value.strip()) > MAX_LABEL_LENGTH:
        return f"Labels are limited to {MAX_LABEL_LENGTH} characters."
    return None


def normalize_icon(value: object) -> str:
    icon = clean_text(value, limit=8)
    return icon or FALLBACK_ICON


def host_port(url: str) -> tuple[str, int]:
    """Derive the display host and port from a stored URL.

    The explicit port wins; otherwise the scheme default is used (80/443), so a
    tile always reads like `media.lan:8096` instead of echoing the whole URL.
    """
    parts = urlsplit(url)
    scheme = (parts.scheme or "").lower()
    host = parts.hostname or ""
    try:
        port = parts.port
    except ValueError:
        port = None
    if port is None:
        port = 443 if scheme == "https" else 80
    return host, port
