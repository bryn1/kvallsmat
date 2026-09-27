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

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import auth_service, profile_service, security
from app.config import get_planner_config
from app.models.store_selection import valid_store_ids
from app.models.users import User
from src.locator import resolve_stores

router = APIRouter(prefix="/api/profile", tags=["profile"])

# Max stores mirrors the profile model / POC store_selection rule (MAX=3).
_MAX_STORES = profile_service.MAX_SELECTED_STORES

# Swedish postnummer: "41451" or "414 51" (T10b §4); normalized to digits-only.
POSTAL_CODE_RE = re.compile(r"^\d{3}\s?\d{2}$")


class ProfileBody(BaseModel):
    persons: int = Field(default=2, ge=1)
    meal_days: int = Field(default=5, ge=1)
    kron_budget: int  # REQUIRED — gate C4 "kron-budget" (missing -> 422)
    selected_stores: list[str] = Field(default_factory=list)
    # MC 1355.16 (T10b §4): ABSENT field = leave the persisted value unchanged
    # (the deployed frontend does not send postal_code today; clear-on-absent
    # would wipe a saved postnummer on a stale-client save — T10d F6). Only an
    # explicit null or "" clears it (and resolved_stores with it).
    postal_code: str | None = None
    # MC 1355.18 (T11): same absent-means-unchanged rule as postal_code —
    # absent = leave the persisted value, explicit null = clear, value = store.
    # num_children is INFORMATIONAL in T11 (does not feed servings planning).
    num_children: int | None = Field(default=None, ge=0)
    prefer_kid_friendly: int | None = Field(default=None, ge=0, le=1)


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

    # MC 1355.16 (T10b §4): postal_code semantics — absent = unchanged,
    # explicit null/"" = clear (and clear resolved_stores), value = resolve now.
    postal_sent = "postal_code" in body.model_fields_set
    existing = profile_service.load_profile(user)
    if postal_sent and body.postal_code:
        if not POSTAL_CODE_RE.fullmatch(body.postal_code.strip()):
            raise HTTPException(
                status_code=422,
                detail="postal_code must be a Swedish postnummer, e.g. "
                       "'414 51' or '41451'")
        postal = re.sub(r"\s", "", body.postal_code)
        resolved = _resolve_or_error(postal)
    elif postal_sent:
        postal, resolved = None, None
    else:
        postal = existing.postal_code if existing else None
        resolved = existing.resolved_stores if existing else None

    # MC 1355.18 (T11): num_children / prefer_kid_friendly — same rule as
    # postal_code: absent = unchanged, explicit null = clear, value = store.
    children_sent = "num_children" in body.model_fields_set
    kid_sent = "prefer_kid_friendly" in body.model_fields_set
    num_children = (body.num_children if children_sent
                    else (existing.num_children if existing else None))
    prefer_kid = (body.prefer_kid_friendly if kid_sent
                  else (existing.prefer_kid_friendly if existing else None))

    data = profile_service.ProfileData(
        persons=body.persons,
        meal_days=body.meal_days,
        kron_budget=body.kron_budget,
        selected_stores=body.selected_stores,
        postal_code=postal,
        resolved_stores=resolved,
        num_children=num_children,
        prefer_kid_friendly=prefer_kid,
    )
    row = profile_service.save_profile(user, data)
    saved = profile_service.load_profile(user)
    # echo the persisted profile back so the PUT->GET roundtrip is provably identical
    return {"saved": True, "profile_id": row.profile_id, "profile": saved.as_dict()}


def _resolve_or_error(postal_code: str) -> dict:
    """Resolve-once at save time (T10b §1). NEVER raises: a locator failure is
    persisted per chain and echoed back, never a 500 (T10b §4)."""
    try:
        return resolve_stores(postal_code)
    except Exception as exc:  # belt: resolve_stores is fail-tolerant per chain
        return {"resolved_at": datetime.now(timezone.utc).isoformat(),
                "chains": {}, "error": f"{type(exc).__name__}: {exc}"}
