"""app.routers.profile — auth-protected /api/profile GET|PUT (Phase 5 T4 profile, gate C4).

The profile is AUTH-SKYDDAD: every handler first resolves the opaque ``matapp_session``
cookie to a logged-in ``users.User`` (reusing Phase 3 ``auth_service.current_user``);
if the cookie is absent/invalid the handler returns **401 — never 200**. This is the
exact gate-C4 line: ``en oautentiserad GET /api/profile ger 401 (inte 200)``.

  GET /api/profile  — read the authenticated user's persisted profile (200 with body,
                      401 when unauthenticated; 404 when logged in but no profile yet).
  PUT /api/profile  — store/update the authenticated user's profile (200 + echo back,
                      401 when unauthenticated, 422 on out-of-range values).

Single concern: HTTP wire-up. Persistence lives in app/profile_service; auth resolution
in app/auth_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import auth_service, profile_service, security
from app.config import get_planner_config
from app.models.store_selection import valid_store_ids
from app.models.users import User

router = APIRouter(prefix="/api/profile", tags=["profile"])

# Max stores mirrors the profile model / POC store_selection rule (MAX=3).
_MAX_STORES = profile_service.MAX_SELECTED_STORES


class ProfileBody(BaseModel):
    persons: int = Field(default=2, ge=1)
    meal_days: int = Field(default=5, ge=1)
    kron_budget: int  # REQUIRED — gate C4 "kron-budget" (missing -> 422)
    selected_stores: list[str] = Field(default_factory=list)


def _current_user_or_401(request: Request) -> User:
    """Resolve the session cookie to a User; 401 when absent/invalid (auth-skyddad)."""
    token = request.cookies.get(security.SESSION_COOKIE)
    user = auth_service.current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


@router.get("")
def get_profile(request: Request,
                user: User = Depends(_current_user_or_401)) -> dict:
    data = profile_service.load_profile(user)
    if data is None:
        raise HTTPException(status_code=404, detail="no profile saved")
    return data.as_dict()


@router.put("")
def put_profile(body: ProfileBody, request: Request,
                user: User = Depends(_current_user_or_401)) -> dict:
    if len(body.selected_stores) > _MAX_STORES:
        raise HTTPException(
            status_code=422,
            detail=f"selected_stores may hold at most {_MAX_STORES} stores",
        )
    # P1-2 fix (MC 1355.3): validate store ids against the SAME PlannerConfig
    # catalog the stores router serves (O1 — one catalog, no second list).
    if len(set(body.selected_stores)) != len(body.selected_stores):
        raise HTTPException(status_code=422,
                            detail="selected_stores must not contain duplicates")
    valid = valid_store_ids(get_planner_config())
    bad = [sid for sid in body.selected_stores if sid not in valid]
    if bad:
        raise HTTPException(status_code=422,
                            detail=f"unknown store_id(s): {bad}")
    data = profile_service.ProfileData(
        persons=body.persons,
        meal_days=body.meal_days,
        kron_budget=body.kron_budget,
        selected_stores=body.selected_stores,
    )
    row = profile_service.save_profile(user, data)
    saved = profile_service.load_profile(user)
    # echo the persisted profile back so the PUT->GET roundtrip is provably identical
    return {"saved": True, "profile_id": row.profile_id, "profile": saved.as_dict()}
