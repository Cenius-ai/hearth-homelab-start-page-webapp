"""Field-level rules for the two writable entities.

Both the JSON API and the plain server-rendered forms run through these, so a
rule can never drift between the two write paths.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from . import repository as repo
from .validate import (
    MAX_LABEL_LENGTH,
    MAX_NAME_LENGTH,
    MAX_URL_LENGTH,
    clean_text,
    normalize_icon,
    validate_label,
    validate_name,
    validate_url,
)


def _coerce_category_id(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


async def parse_service_payload(
    db: aiosqlite.Connection, data: dict[str, Any], *, partial: bool = False
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return (clean values, field errors) for a service create/update."""
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if not partial or "name" in data:
        name_error = validate_name(data.get("name"))
        values["name"] = clean_text(data.get("name"), limit=MAX_NAME_LENGTH)
        if name_error:
            errors["name"] = name_error

    if not partial or "url" in data:
        url_error = validate_url(data.get("url"))
        values["url"] = clean_text(data.get("url"), limit=MAX_URL_LENGTH)
        if url_error:
            errors["url"] = url_error

    if not partial or "category_id" in data:
        category_id = _coerce_category_id(data.get("category_id"))
        if category_id is None:
            errors["category_id"] = "Please choose a category."
        elif not await repo.category_exists(db, category_id):
            errors["category_id"] = "That category no longer exists."
        else:
            values["category_id"] = category_id

    if not partial or "icon" in data:
        values["icon"] = normalize_icon(data.get("icon"))

    return values, errors


def parse_bookmark_payload(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}

    label_error = validate_label(data.get("label"))
    values["label"] = clean_text(data.get("label"), limit=MAX_LABEL_LENGTH)
    if label_error:
        errors["label"] = label_error

    url_error = validate_url(data.get("url"))
    values["url"] = clean_text(data.get("url"), limit=MAX_URL_LENGTH)
    if url_error:
        errors["url"] = url_error

    return values, errors
