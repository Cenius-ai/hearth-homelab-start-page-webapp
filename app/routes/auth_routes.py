"""Login, registration, logout and the two auth pages."""

from __future__ import annotations

from sanic import Blueprint, Request
from sanic.response import json, redirect

from .. import auth, config, ratelimit, validate
from ..db import insert, open_db, query_one
from ..errors import ApiProblem, ValidationFailed
from ..formatting import iso, utcnow
from ..request_utils import json_body
from ..security import hash_password, verify_password
from ..templating import render

bp = Blueprint("auth", url_prefix="/")

INVALID_CREDENTIALS = "Email or password is incorrect"


def safe_next(candidate: str | None) -> str:
    """Only ever redirect to a local path after sign-in."""
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return "/"
    return candidate


@bp.get("/login")
async def login_page(request: Request):
    if auth.current_user(request):
        return redirect(safe_next(request.args.get("next")))
    return render(
        request,
        "login.html",
        page_title="Sign in — Hearth Homelab Start Page",
        next_path=safe_next(request.args.get("next")),
    )


@bp.get("/register")
async def register_page(request: Request):
    if auth.current_user(request):
        return redirect("/")
    return render(request, "register.html", page_title="Create account — Hearth Homelab Start Page")


@bp.post("/api/auth/login")
async def api_login(request: Request):
    data = await json_body(request)
    email = validate.clean_text(data.get("email"), limit=254).lower()
    password = data.get("password") if isinstance(data.get("password"), str) else ""

    errors: dict[str, str] = {}
    email_error = validate.validate_email(email)
    if email_error:
        errors["email"] = email_error
    if not password:
        errors["password"] = "Please enter your password."
    if errors:
        raise ValidationFailed(errors)

    if not ratelimit.ip_limiter.allow(ratelimit.client_ip(request)) or not ratelimit.account_limiter.allow(
        f"account:{email}"
    ):
        raise ApiProblem(429, "too_many_attempts", message="Too many attempts. Try again in a minute.")

    async with open_db() as db:
        row = await query_one(
            db, "SELECT id, email, password_hash, salt FROM users WHERE email = ?", (email,)
        )
        if row is None or not verify_password(password, row["salt"], row["password_hash"]):
            raise ApiProblem(401, "invalid_credentials", message=INVALID_CREDENTIALS)

        # Rotate: a cookie presented to the login form never survives the login.
        previous = request.cookies.get(config.SESSION_COOKIE)
        if previous:
            await auth.destroy_session(db, previous)
        token, _ = await auth.create_session(db, row["id"])
        user = {"id": row["id"], "email": row["email"]}

    response = json({"user": user, "redirect_to": "/"})
    auth.set_session_cookie(response, token)
    return response


@bp.post("/api/auth/register")
async def api_register(request: Request):
    data = await json_body(request)
    email = validate.clean_text(data.get("email"), limit=254).lower()
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    confirm = data.get("confirm_password") if isinstance(data.get("confirm_password"), str) else ""

    errors: dict[str, str] = {}
    email_error = validate.validate_email(email)
    if email_error:
        errors["email"] = email_error
    password_error = validate.validate_password(password)
    if password_error:
        errors["password"] = password_error
    elif confirm and confirm != password:
        errors["confirm_password"] = "Passwords do not match."
    elif not confirm:
        errors["confirm_password"] = "Please confirm your password."
    if errors:
        raise ValidationFailed(errors)

    if not ratelimit.ip_limiter.allow(ratelimit.client_ip(request)):
        raise ApiProblem(429, "too_many_attempts", message="Too many attempts. Try again in a minute.")

    async with open_db() as db:
        existing = await query_one(db, "SELECT id FROM users WHERE email = ?", (email,))
        if existing is not None:
            raise ValidationFailed({"email": "That email is already registered."})
        password_hash, salt = hash_password(password)
        user_id = await insert(
            db,
            "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, salt, iso(utcnow())),
        )
        token, _ = await auth.create_session(db, user_id)

    response = json({"user": {"id": user_id, "email": email}, "redirect_to": "/"}, status=201)
    auth.set_session_cookie(response, token)
    return response


@bp.post("/api/auth/logout")
async def api_logout(request: Request):
    auth.require_user(request)
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        async with open_db() as db:
            await auth.destroy_session(db, token)
    response = json({"ok": True})
    auth.clear_session_cookie(response)
    return response


@bp.post("/logout")
async def logout_form(request: Request):
    """The no-JavaScript sign-out path used by the rail's Sign out button."""
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        async with open_db() as db:
            await auth.destroy_session(db, token)
    response = redirect("/login", status=303)
    auth.clear_session_cookie(response)
    return response
