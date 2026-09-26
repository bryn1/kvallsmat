"""app.routers.stores — stores router for the web-api (ported from the deployed
hosting copy, MC 1355.3 T3; origin: hosting/apps/matapp app/routers/stores.py).

  GET  /api/stores        -> catalog READ from the motor's PlannerConfig grocers
                             at request time (O1 pin — no app-side second list).
                             MC 1355.16: optional ``?postal_code=`` resolve-
                             preview — AUTH-GATED (401 anonymous, same gate as
                             profile/menu, T10b §10-F5); anonymous calls without
                             the param keep today's byte-identical behavior.
  POST /api/stores/select -> replace-all the chosen stores, capped at 3
                             (store_selection.upsert_selection). >3 or unknown
                             store_id -> 422.
  GET  /api/stores/selected -> the currently selected stores (persisted).

The persistence table is store_selection, created on the shared database.Base at
boot. Core business rules live in the store_selection module — this router only
marshals HTTP<->session.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth_service
from app.config import get_planner_config
from app.db import get_db
from app.models.store_selection import (
    list_selected,
    upsert_selection,
    MAX_SELECTED,
)
# MC 1355.17 (T10f DA P2-2): the preview param is validated + normalized by the
# SAME regex/normalization the profile PUT uses — one postnummer rule, no second.
from app.routers.profile import POSTAL_CODE_RE
from src.locator import resolve_stores_cached

router = APIRouter(prefix="/api/stores", tags=["stores"])

MAX_SELECTED_REACHABLE = MAX_SELECTED  # min(MAX_SELECTED, real grocers)


class StoreSelectIn(BaseModel):
    store_ids: list[str] = Field(default_factory=list)


def _catalog(config):
    """Map PlannerConfig grocers -> public store payload (READ at request time)."""
    return [
        {
            "store_id": g.grocer_id,
            "name": g.grocer_id,           # motor exposes no display name field
            "chain_type": g.chain,
            "enabled": True,               # motor has no disabled flag per grocer
        }
        for g in config.grocers
    ]


@router.get("")
def list_stores(request: Request,
                postal_code: str | None = Query(default=None),
                session: Session = Depends(get_db)):
    """Store catalog; with ``?postal_code=`` an auth-gated resolve-preview.

    The preview param is honored ONLY for an authenticated user (401 when
    anonymous — T10b §10-F5: the locator pipeline, Nominatim 1 req/s policy
    included, is never reachable anonymously). The resolve result is served
    from the bounded per-process cache (TTL 24 h, max 128 entries — T10d N4).
    """
    cfg = get_planner_config()
    catalog = _catalog(cfg)
    if postal_code is None:
        return catalog  # anonymous behavior byte-identical to today
    auth_service.current_user_or_401(request)
    # MC 1355.17 (T10f DA P2-2): same validation + digits-only normalization as
    # PUT /api/profile — a malformed param is a 422, never a raw Nominatim query.
    if not POSTAL_CODE_RE.fullmatch(postal_code.strip()):
        raise HTTPException(
            status_code=422,
            detail="postal_code must be a Swedish postnummer, e.g. "
                   "'414 51' or '41451'")
    return {"stores": catalog,
            "nearby": resolve_stores_cached(re.sub(r"\s", "", postal_code))}


@router.post("/select")
def select_stores(payload: StoreSelectIn,
                  session: Session = Depends(get_db)) -> dict:
    cfg = get_planner_config()
    if len(payload.store_ids) > MAX_SELECTED:
        raise HTTPException(status_code=422,
                            detail=f"at most {MAX_SELECTED} stores can be selected")
    try:
        keep = upsert_selection(session, payload.store_ids, config=cfg)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return {"selected": keep}


@router.get("/selected")
def get_selected(session: Session = Depends(get_db)) -> list[dict]:
    rows = list_selected(session)
    return [{"store_id": r.store_id, "selected_at": r.selected_at.isoformat()}
            for r in rows]
