"""GET /api/bootstrap - the single dashboard payload."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json

from .. import auth, repository as repo
from ..db import open_db

bp = Blueprint("bootstrap", url_prefix="/api/bootstrap")


@bp.get("")
async def bootstrap(request):
    user = auth.require_user(request)
    async with open_db() as db:
        payload = await repo.build_dashboard(db, user)
    return json(payload)
