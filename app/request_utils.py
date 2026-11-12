"""Small request-parsing helpers shared by the route modules."""

from __future__ import annotations

import json
from typing import Any

from sanic import Request

from .errors import ValidationFailed


async def json_body(request: Request) -> dict[str, Any]:
    """Parse a JSON object body, or raise a 422 with a readable message."""
    raw = request.body or b""
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValidationFailed({"_": "Request body must be valid JSON."})
    if not isinstance(data, dict):
        raise ValidationFailed({"_": "Request body must be a JSON object."})
    return data


def form_value(request: Request, key: str, default: str = "") -> str:
    """Read a single value from an HTML form submission.

    Sanic's RequestParameters.get already returns the first value of the list.
    """
    value = request.form.get(key, default)
    return value if isinstance(value, str) else default
