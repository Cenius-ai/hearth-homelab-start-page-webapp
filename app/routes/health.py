"""Public liveness route.

It is unauthenticated on purpose: container health checks use it, and the seeded
"Hearth (this page)" tile probes it so its status dot reflects something real.
"""

from __future__ import annotations

from sanic import Blueprint
from sanic.response import json

from .. import config
from ..formatting import iso, utcnow

bp = Blueprint("health", url_prefix="/")


@bp.get("/healthz")
async def healthz(request):
    return json(
        {
            "status": "ok",
            "app": "hearth",
            "version": config.APP_VERSION,
            "time": iso(utcnow()),
        }
    )
