"""Server-rendered screens: dashboard, service list, service detail, forms, log."""

from __future__ import annotations

from typing import Any

from sanic import Blueprint, Request
from sanic.response import redirect

from .. import auth, repository as repo
from ..db import open_db
from ..request_utils import form_value
from ..service_rules import parse_service_payload
from ..templating import render

bp = Blueprint("pages", url_prefix="/")


def _status_counts(services: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(services), "up": 0, "down": 0, "unknown": 0}
    for service in services:
        health = service.get("health")
        if not health:
            counts["unknown"] += 1
        elif health.get("status") == "up":
            counts["up"] += 1
        else:
            counts["down"] += 1
    return counts


async def _form_context(db, *, values: dict[str, Any], errors: dict[str, str], **extra) -> dict[str, Any]:
    categories = await repo.list_categories(db)
    context = {
        "categories": categories,
        "values": values,
        "errors": errors,
        "selected_category": str(values.get("category_id") or ""),
    }
    context.update(extra)
    return context


@bp.get("/")
async def dashboard(request: Request):
    user = auth.require_user(request)
    async with open_db() as db:
        payload = await repo.build_dashboard(db, user)
    return render(
        request,
        "dashboard.html",
        page_title="Hearth Homelab Start Page",
        dashboard=payload,
        counts=_status_counts(payload["services"]),
        categories=payload["categories"],
    )


@bp.get("/services")
async def services_page(request: Request):
    auth.require_user(request)
    async with open_db() as db:
        categories = await repo.list_categories(db)
        services = await repo.list_services(db)
        health = await repo.latest_health(db)
    names = {category["id"]: category["name"] for category in categories}
    groups = []
    for category in categories:
        rows = [
            {**repo.service_payload(service, health.get(service["id"])), "category_name": category["name"]}
            for service in services
            if service["category_id"] == category["id"]
        ]
        rows.sort(key=lambda row: (row["sort_order"], row["id"]))
        if rows:
            groups.append({"name": category["name"], "services": rows})
    payload_services = [service for group in groups for service in group["services"]]
    return render(
        request,
        "services_list.html",
        page_title="All services — Hearth Homelab Start Page",
        groups=groups,
        counts=_status_counts(payload_services),
        category_count=len(groups),
        names=names,
    )


@bp.get("/services/new")
async def service_new_page(request: Request):
    auth.require_user(request)
    async with open_db() as db:
        context = await _form_context(
            db,
            values={"name": "", "url": "", "icon": "", "category_id": ""},
            errors={},
            form_action="/services/new",
            form_title="Add a service",
            submit_label="Add service",
            service=None,
        )
    return render(request, "service_form.html", page_title="Add a service — Hearth Homelab Start Page", **context)


@bp.post("/services/new")
async def service_new_submit(request: Request):
    auth.require_user(request)
    submitted = {
        "name": form_value(request, "name"),
        "url": form_value(request, "url"),
        "category_id": form_value(request, "category_id"),
        "icon": form_value(request, "icon"),
    }
    async with open_db() as db:
        values, errors = await parse_service_payload(db, submitted)
        if errors:
            context = await _form_context(
                db,
                values=submitted,
                errors=errors,
                form_action="/services/new",
                form_title="Add a service",
                submit_label="Add service",
                service=None,
            )
            return render(
                request,
                "service_form.html",
                status=422,
                page_title="Add a service — Hearth Homelab Start Page",
                **context,
            )
        service = await repo.create_service(db, **values)
    return redirect(f"/services/{service['id']}", status=303)


@bp.get("/services/<service_id:int>")
async def service_detail(request: Request, service_id: int):
    auth.require_user(request)
    async with open_db() as db:
        service = await repo.get_service(db, service_id)
        if service is None:
            return render(request, "not_found.html", status=404, page_title="Service not found — Hearth Homelab Start Page")
        health = await repo.latest_health_for(db, service_id)
        history = await repo.check_history(db, service_id)
        categories = await repo.list_categories(db)
    category_name = next(
        (category["name"] for category in categories if category["id"] == service["category_id"]),
        "Uncategorised",
    )
    return render(
        request,
        "service_detail.html",
        page_title=f"{service['name']} — Hearth Homelab Start Page",
        service=repo.service_payload(service, health),
        category_name=category_name,
        history=history,
    )


@bp.get("/services/<service_id:int>/edit")
async def service_edit_page(request: Request, service_id: int):
    auth.require_user(request)
    async with open_db() as db:
        service = await repo.get_service(db, service_id)
        if service is None:
            return render(request, "not_found.html", status=404, page_title="Service not found — Hearth Homelab Start Page")
        context = await _form_context(
            db,
            values=service,
            errors={},
            form_action=f"/services/{service_id}/edit",
            form_title=f"Edit {service['name']}",
            submit_label="Save changes",
            service=service,
        )
    return render(request, "service_form.html", page_title=f"Edit {service['name']} — Hearth Homelab Start Page", **context)


@bp.post("/services/<service_id:int>/edit")
async def service_edit_submit(request: Request, service_id: int):
    auth.require_user(request)
    submitted = {
        "name": form_value(request, "name"),
        "url": form_value(request, "url"),
        "category_id": form_value(request, "category_id"),
        "icon": form_value(request, "icon"),
    }
    async with open_db() as db:
        service = await repo.get_service(db, service_id)
        if service is None:
            return render(request, "not_found.html", status=404, page_title="Service not found — Hearth Homelab Start Page")
        values, errors = await parse_service_payload(db, submitted)
        if errors:
            context = await _form_context(
                db,
                values={**service, **submitted},
                errors=errors,
                form_action=f"/services/{service_id}/edit",
                form_title=f"Edit {service['name']}",
                submit_label="Save changes",
                service=service,
            )
            return render(
                request,
                "service_form.html",
                status=422,
                page_title=f"Edit {service['name']} — Hearth Homelab Start Page",
                **context,
            )
        await repo.update_service(db, service_id, values)
    return redirect(f"/services/{service_id}", status=303)


@bp.post("/services/<service_id:int>/delete")
async def service_delete(request: Request, service_id: int):
    auth.require_user(request)
    async with open_db() as db:
        service = await repo.get_service(db, service_id)
        if service is None:
            return render(request, "not_found.html", status=404, page_title="Service not found — Hearth Homelab Start Page")
        await repo.delete_service(db, service_id)
    return redirect("/services", status=303)


@bp.get("/activity")
async def activity_page(request: Request):
    auth.require_user(request)
    async with open_db() as db:
        checks = await repo.recent_checks(db, limit=60)
        health = await repo.latest_health(db)
        services = await repo.list_services(db)
    payload_services = [repo.service_payload(service, health.get(service["id"])) for service in services]
    return render(
        request,
        "activity.html",
        page_title="Check log — Hearth Homelab Start Page",
        checks=checks,
        counts=_status_counts(payload_services),
    )
