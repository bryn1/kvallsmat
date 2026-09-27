"""app.routers.menu — auth-/profil-skyddad GET /api/menu (Phase 7 T6, MC 1355.5).

The API-lager's headline endpoint: a logged-in user asks for a week's menu and gets
THREE candidate plans (suggestions). MC 1355.5 rewires the data source: the offers
are read from the OFFERS DB (``src/offers_db/store.list_offers_in_week``), filtered
to the user's selected stores (store_selection), and handed to the motor's real
planner ``src.planner.menu.plan_menu`` — the hardcoded ``app/optimizer/offers.py``
fixture list is no longer the menu's data source.

  * AUTH: every handler first resolves the opaque ``matapp_session`` cookie to a
    logged-in ``users.User`` via Phase 3 ``auth_service.current_user``; absent/invalid
    cookie -> **401, never 200** (the exact gate-C6 line "utan session 401").
  * PROFIL: the suggestion families are built from the authenticated user's own
    persisted profile (persons, meal_days) via Phase 5 ``profile_service.load_profile``
    — Phase-6 FamilyPrefs defaults (persons=4, meal_days=5) when nothing is saved.
  * WEEK: optional ``?week=YYYY-Www`` (default = current ISO week). The pattern is
    enforced by FastAPI (422 on a malformed key) and the key is validated as a REAL
    week via the ONE shared helper ``src.planner.weeks.week_to_monday`` — the audit's
    latent BUG-1/BUG-2 (``9999-W99`` OverflowError, ``2026-W54`` silent extrapolation)
    is fixed at this boundary with a 422, never a 500.
  * DEGRADATION (N5): an empty offers DB still returns 200 — every day degrades to
    ``used_offer_ids: []`` (the motor planner's recipe-only path), never a 500.

Response is pydantic-validated (gate C6 "pydantic-validering"): MenuResponse with a
list[Suggestion], each suggestion the {seed, week_key, days[]} shape.

Single concern: HTTP wire-up + planner invocation. Auth/persistence live in the
service modules; the week math lives in src/planner/weeks.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import auth_service, db, profile_service, security
from app.models.store_selection import list_selected
from app.models.users import User
from app.optimizer.optimizer import DEFAULT_SEEDS, FamilyPrefs, andel_extrapris
from app.optimizer.recipes import recipes
from src.offers_db.store import list_offers_in_week
from src.planner.menu import plan_menu
from src.planner.weeks import current_week_key, week_to_monday

router = APIRouter(prefix="/api/menu", tags=["menu"])

# Gate C6 contract: exactly three suggestions (the Phase 6 DEFAULT_SEEDS = 3 seeds).
SUGGESTION_COUNT = 3
# Display week keys are ISO 8601 week dates, e.g. "2026-W34" (1-2 digit week is
# accepted by the pattern; real-week validity is checked by week_to_monday).
WEEK_PATTERN = r"^\d{4}-W\d{1,2}$"


# ---------------------------------------------------------------------------
# Pydantic response models (gate C6 "pydantic-validering")
# ---------------------------------------------------------------------------


class MenuDay(BaseModel):
    date: str
    dish_id: str
    andel_extrapris: float
    used_offer_ids: list[int] = Field(default_factory=list)
    # MC 1355.18 (T11): additive field (same precedent as offer_sources) —
    # absent/false renders nothing in the UI, old responses stay valid.
    kid_friendly: bool = False


class Suggestion(BaseModel):
    week_key: str
    seed: int
    days: list[MenuDay]


class OfferSource(BaseModel):
    """Which offer row (and store scope) fed the plan — MC 1355.16 (T10b §4).

    MC 1355.17 (T10f DA P3-2): ``store_name`` carries the resolved store's
    display name so the UI shows "butik: Willys Majorna", not a raw id.
    """

    offer_id: int
    grocer_id: str
    store_id: str | None = None
    store_name: str | None = None


class MenuResponse(BaseModel):
    week_key: str
    suggestions: list[Suggestion] = Field(default_factory=list)
    # MC 1355.16: optional additive field; used_offer_ids kept unchanged for
    # response-shape compatibility.
    offer_sources: list[OfferSource] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Auth dependency (mirrors app/routers/profile.py — 401, never 200)
# ---------------------------------------------------------------------------


def _current_user_or_401(request: Request) -> User:
    """Resolve the session cookie to a User; 401 when absent/invalid (auth-skyddad)."""
    token = request.cookies.get(security.SESSION_COOKIE)
    user = auth_service.current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------


@router.get("", response_model=MenuResponse)
def get_menu(request: Request,
             week: str | None = Query(default=None, pattern=WEEK_PATTERN),
             user: User = Depends(_current_user_or_401),
             session=Depends(db.get_db)) -> MenuResponse:
    """Plan the week's menu from the offers DB for the authenticated user's household."""

    # WEEK: default = current ISO week; validate as a REAL week (BUG-1/BUG-2 fix).
    week_key = week or current_week_key()
    try:
        week_to_monday(week_key)
    except ValueError:
        raise HTTPException(status_code=422,
                            detail=f"week is not a real ISO week: {week_key!r}") from None

    # OFFERS from the DB, filtered to the user's selected stores (empty selection
    # = no filter yet: the user has not chosen stores, so the whole week is offered).
    offers = list_offers_in_week(session, week_key)
    selected = [s.store_id for s in list_selected(session)]
    if selected:
        offers = [o for o in offers if o.grocer_id in selected]

    # PROFIL-skyddad: build the family from THIS user's saved profile.
    profile = profile_service.load_profile(user)
    persons = profile.persons if profile is not None else FamilyPrefs().persons
    meal_days = profile.meal_days if profile is not None else FamilyPrefs().meal_days
    family = FamilyPrefs(meal_days=meal_days, persons=persons,
                         prefer_kid_friendly=bool(
                             profile.prefer_kid_friendly or 0)
                         if profile is not None else False)

    # MC 1355.16 (T10b §4): store-level selection — the store clause keeps a
    # chain-level row (store_id NULL = valid everywhere) or a row scoped to one
    # of the profile's resolved stores; then dedup by (grocer_id, normalized
    # name) preferring the store-level row. No resolved stores (or no
    # postal_code) -> both steps are a no-op and behavior is exactly today's.
    resolved = profile.resolved_stores if profile is not None else None
    offers = _apply_store_clause(offers, resolved)
    offers = _dedup_by_name(offers, resolved)
    # MC 1355.17 (T10f DA P3-2): store_id -> display name from the persisted
    # resolution, so offer_sources can show the store NAME in the UI.
    store_names = _resolved_store_names(resolved)
    offer_sources = [
        {"offer_id": o.offer_id, "grocer_id": o.grocer_id,
         "store_id": o.store_id,
         "store_name": store_names.get(str(o.store_id)) if o.store_id else None}
        for o in offers
    ]

    # The motor's real planner (src/planner/menu.py) — one plan per seed.
    recipe_roster = recipes()
    by_title = {r.title: r for r in recipe_roster}
    plans = [plan_menu(week_key, offers, recipe_roster, family, seed=seed)
             for seed in DEFAULT_SEEDS]

    # Pydantic validates + shapes the response (gate C6). ``andel_extrapris`` is
    # kept for response-shape compatibility; the offers DB carries no reference
    # price column, so the ratio is computed from what the rows actually hold.
    suggestions = [
        Suggestion(
            week_key=p["week_key"],
            seed=seed,
            days=[
                MenuDay(
                    date=d["date"],
                    dish_id=d["dish_id"],
                    andel_extrapris=(
                        round(andel_extrapris(by_title[d["dish_id"]], offers), 4)
                        if d["dish_id"] in by_title else 0.0
                    ),
                    used_offer_ids=d["used_offer_ids"],
                    kid_friendly=bool(
                        (getattr(by_title[d["dish_id"]], "kid_friendly", 0) or 0)
                    ) if d["dish_id"] in by_title else False,
                )
                for d in p["days"]
            ],
        )
        for seed, p in zip(DEFAULT_SEEDS, plans)
    ]
    return MenuResponse(week_key=week_key, suggestions=suggestions,
                        offer_sources=offer_sources)


# ---------------------------------------------------------------------------
# Store-level selection helpers (MC 1355.16, T10b §4)
# ---------------------------------------------------------------------------


def _resolved_chain_ids(resolved: dict | None, chain: str) -> list[str]:
    """Store ids resolved for *chain*; [] when absent or the chain errored.

    An errored chain contributes chain-level rows only (T10b §4) — which the
    store clause below expresses by matching no store-scoped ids.
    """
    if not isinstance(resolved, dict):
        return []
    entry = (resolved.get("chains") or {}).get(chain) or {}
    if entry.get("status") != "ok":
        return []
    return [str(s.get("store_id")) for s in entry.get("stores", [])
            if s.get("store_id") is not None]


def _resolved_store_names(resolved: dict | None) -> dict:
    """store_id -> store_name across ALL resolved chains (T10f DA P3-2).

    Empty when unresolved/malformed — the UI then falls back to the raw id.
    """
    names: dict = {}
    if not isinstance(resolved, dict):
        return names
    for entry in (resolved.get("chains") or {}).values():
        if not isinstance(entry, dict) or entry.get("status") != "ok":
            continue
        for store in entry.get("stores") or []:
            sid = store.get("store_id")
            name = store.get("store_name")
            if sid is not None and name:
                names[str(sid)] = str(name)
    return names


def _apply_store_clause(offers: list, resolved: dict | None) -> list:
    """Keep an offer when chain-level (store_id NULL) or scoped to a resolved
    store of its own chain (T10b §4 step 1). No resolved stores at all -> a
    no-op: behavior is exactly today's (the regression guard)."""
    if not isinstance(resolved, dict) or not resolved.get("chains"):
        return offers
    kept = []
    for offer in offers:
        ids = _resolved_chain_ids(resolved, offer.grocer_id)
        if offer.store_id is None or str(offer.store_id) in ids:
            kept.append(offer)
    return kept


def _dedup_by_name(offers: list, resolved: dict | None) -> list:
    """Dedup (grocer_id, normalized name) preferring the store-level row
    (T10b §4 step 2). Normalized = casefold + strip (T10d N3). Chains without
    resolved stores are left untouched — the byte-identical no-op regression
    guard — so plan_menu's offer-hit counting and andel_extrapris never
    double-count the same physical product that exists both chain-level and
    store-level."""
    best: dict = {}
    ordered: list = []
    for offer in offers:
        if not _resolved_chain_ids(resolved, offer.grocer_id):
            ordered.append(offer)  # untouched chain: never deduped
            continue
        key = (offer.grocer_id, (offer.name or "").casefold().strip())
        current = best.get(key)
        if current is None:
            best[key] = offer
            ordered.append(offer)
        elif offer.store_id is not None and current.store_id is None:
            best[key] = offer  # store-level row wins; keep its position
            ordered[ordered.index(current)] = offer
    return ordered
