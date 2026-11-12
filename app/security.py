"""Password hashing and session-token helpers.

Passwords: PBKDF2-HMAC-SHA256, 120000 iterations, 16-byte per-user random salt,
both stored hex encoded. Session tokens are opaque 32-byte urlsafe strings; the
database only ever stores their sha256 hash.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 120_000
SALT_BYTES = 16


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Return (password_hash_hex, salt_hex) for a plaintext password."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    """Constant-time check of a password against a stored salt + hash."""
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), expected_hash)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
