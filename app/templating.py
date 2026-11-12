"""Jinja rendering helpers.

Server-rendered templates are the source of truth for first paint: the tile
grid, bookmarks and tables all exist in the HTML before any JavaScript runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sanic import Request
from sanic.response import html

from . import config, formatting

TEMPLATES_DIR = Path(__file__).with_name("templates")

# Rail navigation. `icon` is an inline SVG path (stroke, 24x24 viewBox) so the
# chrome uses one icon set rather than emoji.
NAV_ITEMS: list[dict[str, str]] = [
    {
        "href": "/",
        "label": "Start page",
        "icon": "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H10v6H4a1 1 0 0 1-1-1z",
    },
    {
        "href": "/services",
        "label": "All services",
        "icon": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    },
    {"href": "/services/new", "label": "Add service", "icon": "M12 5v14M5 12h14"},
    {
        "href": "/activity",
        "label": "Check log",
        "icon": "M3 12h4l3 8 4-16 3 8h4",
    },
]

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
env.globals.update(
    relative_time=formatting.relative_time,
    status_label=formatting.status_label,
    status_detail=formatting.status_detail,
    status_tone=formatting.status_tone,
    app_version=config.APP_VERSION,
    demo_email=config.DEMO_EMAIL,
    demo_password=config.DEMO_PASSWORD,
    second_demo_email=config.SECOND_DEMO_EMAIL,
    second_demo_password=config.SECOND_DEMO_PASSWORD,
    nav_items=NAV_ITEMS,
)


def active_nav(path: str) -> str:
    """The href of the nav item whose prefix matches the current path."""
    best = ""
    for item in NAV_ITEMS:
        href = item["href"]
        if href == "/":
            if path == "/":
                best = href
        elif path == href or path.startswith(href):
            if len(href) > len(best):
                best = href
    return best


def render(request: Request, template_name: str, *, status: int = 200, **context: Any):
    """Render a template with the context every page shares."""
    base = {
        "user": getattr(request.ctx, "user", None),
        "current_path": request.path,
        "active_nav": active_nav(request.path),
        "signed_in_email": (getattr(request.ctx, "user", None) or {}).get("email", ""),
    }
    base.update(context)
    return html(env.get_template(template_name).render(**base), status=status)

