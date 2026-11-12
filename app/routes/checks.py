"""On-demand health recheck: POST /api/services/{id}/check."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json

from .. import auth, probe, repository as repo
from ..db import open_db
from ..errors import NotFound

bp = Blueprint("checks", url_prefix="/api/services")


@bp.post("/<service_id:int>/check")
async def check_service(request, service_id: int):
    auth.require_user(request)
    async with open_db() as db:
        service = await repo.get_service(db, service_id)
        if service is None:
            raise NotFound("service_not_found")
        result = await probe.probe(service["url"])
        health = await repo.record_health_check(
            db,
            service_id,
            status=result["status"],
            latency_ms=result["latency_ms"],
            message=result["message"],
        )
    return json({"service_id": service_id, "health": health})
