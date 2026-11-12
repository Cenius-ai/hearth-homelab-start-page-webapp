"""Per-user bookmarks API."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import empty, json

from .. import auth, repository as repo
from ..db import open_db
from ..errors import NotFound, ValidationFailed
from ..request_utils import json_body
from ..service_rules import parse_bookmark_payload

bp = Blueprint("bookmarks_api", url_prefix="/api/bookmarks")


@bp.post("")
async def create_bookmark(request):
    user = auth.require_user(request)
    data = await json_body(request)
    values, errors = parse_bookmark_payload(data)
    if errors:
        raise ValidationFailed(errors)
    async with open_db() as db:
        bookmark = await repo.create_bookmark(
            db, user["id"], label=values["label"], url=values["url"]
        )
    return json({"bookmark": bookmark}, status=201)


@bp.delete("/<bookmark_id:int>")
async def delete_bookmark(request, bookmark_id: int):
    user = auth.require_user(request)
    async with open_db() as db:
        deleted = await repo.delete_bookmark(db, user["id"], bookmark_id)
    if not deleted:
        # Same answer as "never existed": a foreign id must not leak its owner.
        raise NotFound("bookmark_not_found")
    return empty(status=204)
