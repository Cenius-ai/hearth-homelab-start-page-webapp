"""Per-user tile order: PUT /api/layout."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json

from .. import auth, repository as repo
from ..db import open_db
from ..errors import ValidationFailed
from ..request_utils import json_body

bp = Blueprint("layout_api", url_prefix="/api/layout")


def _coerce_ids(raw) -> list[int] | None:
    if not isinstance(raw, list):
        return None
    ids: list[int] = []
    for item in raw:
        if isinstance(item, bool):
            return None
        if isinstance(item, int):
            ids.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            ids.append(int(item.strip()))
        else:
            return None
    return ids


@bp.put("")
async def save_layout(request):
    user = auth.require_user(request)
    data = await json_body(request)

    service_ids = _coerce_ids(data.get("service_ids"))
    if service_ids is None:
        raise ValidationFailed({"service_ids": "Send an ordered array of service ids."})
    if len(set(service_ids)) != len(service_ids):
        raise ValidationFailed({"service_ids": "Each service id may appear only once."})

    async with open_db() as db:
        known = await repo.existing_service_ids(db, service_ids)
        missing = [service_id for service_id in service_ids if service_id not in known]
        if missing:
            raise ValidationFailed({"service_ids": "One of those services no longer exists."})
        await repo.save_layout(db, user["id"], service_ids)

    return json({"layout": service_ids})
