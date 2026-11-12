"""Service CRUD API."""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import empty, json

from .. import auth, repository as repo
from ..db import open_db
from ..errors import NotFound, ValidationFailed
from ..request_utils import json_body
from ..service_rules import parse_service_payload

bp = Blueprint("services_api", url_prefix="/api/services")


@bp.post("")
async def create_service(request):
    auth.require_user(request)
    data = await json_body(request)
    async with open_db() as db:
        values, errors = await parse_service_payload(db, data)
        if errors:
            raise ValidationFailed(errors)
        service = await repo.create_service(db, **values)
        health = await repo.latest_health_for(db, service["id"])
    return json({"service": repo.service_payload(service, health)}, status=201)


@bp.patch("/<service_id:int>")
async def update_service(request, service_id: int):
    auth.require_user(request)
    data = await json_body(request)
    async with open_db() as db:
        existing = await repo.get_service(db, service_id)
        if existing is None:
            raise NotFound("service_not_found")
        values, errors = await parse_service_payload(db, data, partial=True)
        if errors:
            raise ValidationFailed(errors)
        updated = await repo.update_service(db, service_id, values)
        if updated is None:
            raise NotFound("service_not_found")
        health = await repo.latest_health_for(db, service_id)
    return json({"service": repo.service_payload(updated, health)})


@bp.delete("/<service_id:int>")
async def delete_service(request, service_id: int):
    auth.require_user(request)
    async with open_db() as db:
        deleted = await repo.delete_service(db, service_id)
    if not deleted:
        raise NotFound("service_not_found")
    return empty(status=204)
