"""app.routers.auth — /api/auth/login|logout|me (Phase 3 T2 auth, gate C2).

The three endpoints the gate C2 names, wired to app.auth_service (session logic) and
app.security (Argon2id + cookie policy):

  POST /api/auth/login   — body {username,password}; on success set the opaque
                           HttpOnly+Secure+SameSite session cookie; 401 on bad creds.
  POST /api/auth/logout  — invalidate the session and clear the cookie (idempotent).
  GET  /api/auth/me      — return the current user from the session cookie; 401 if
                           unauthenticated.

Single concern: HTTP wire-up. No password hashing here (that is app/security's job).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app import auth_service, security

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
    token = auth_service.login(body.username, body.password)
    if token is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    _set_session_cookie(response, token)
    return {"ok": True, "username": body.username}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    auth_service.logout(_read_token(request))
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    user = auth_service.current_user(_read_token(request))
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return {"user_id": user.user_id, "username": user.username}
