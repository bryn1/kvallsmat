"""app.routers.auth — /api/auth/login|logout|me|register (Phase 3 T2 auth, gate C2).

The gate C2 endpoints, wired to app.auth_service (session logic) and
app.security (Argon2id + cookie policy):

  POST /api/auth/login    — body {username,password}; on success set the opaque
                            HttpOnly+Secure+SameSite session cookie; 401 on bad creds.
  POST /api/auth/logout   — invalidate the session and clear the cookie (idempotent).
  GET  /api/auth/me       — return the current user from the session cookie; 401 if
                            unauthenticated.
  POST /api/auth/register — open registration (MC 1355.7, owner-ratified): create
                            the account (argon2id via app.security) and auto-login
                            with the SAME session cookie; 409 duplicate username,
                            422 weak/short password.

Single concern: HTTP wire-up. No password hashing here (that is app/security's job).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth_service, security
from app.auth_service import LoginLockedOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


def _read_token(request: Request) -> str | None:
    return request.cookies.get(security.SESSION_COOKIE)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        security.SESSION_COOKIE,
        token,
        httponly=security.SESSION_HTTPONLY,
        secure=security.SESSION_SECURE,
        samesite=security.SESSION_SAMESITE,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(security.SESSION_COOKIE)


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    try:
        token = auth_service.login(body.username, body.password)
    except LoginLockedOut:
        # F2 (audit 1188): too many failed logins for this username — refuse
        # without touching the DB until the lockout expires.
        raise HTTPException(status_code=429, detail="too many failed logins; try again later")
    if token is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    _set_session_cookie(response, token)
    return {"ok": True, "username": body.username}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    auth_service.logout(_read_token(request))
    _clear_session_cookie(response)
    return {"ok": True}


@router.post("/register")
def register(body: LoginBody, response: Response) -> dict:
    """Open registration (MC 1355.7, owner-ratified): create the account and
    auto-login — the session cookie is set exactly like login's."""
    try:
        token = auth_service.register(body.username, body.password)
    except auth_service.UsernameTaken:
        raise HTTPException(status_code=409, detail="username already taken")
    except auth_service.WeakPassword as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    _set_session_cookie(response, token)
    return {"ok": True, "username": body.username.strip()}


@router.get("/me")
def me(request: Request) -> dict:
    user = auth_service.current_user(_read_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return {"user_id": user.user_id, "username": user.username}
