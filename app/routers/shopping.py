"""app.routers.shopping — auth-gated weekly shopping list + memory + staples
(MC 10037 P1-b/P2-a/P2-b; algorithms ported from matapp per PORT-PLAN).

  * GET    /api/shopping?week=YYYY-Www   default current week; 422 non-real week
                                         (same BUG-1/BUG-2 boundary as menu).
                                         On a FRESH week (no rows yet) due
                                         staples + due habitual memory items
                                         are injected once, deduped (staples
                                         win on a name collision — matapp rule).
  * POST   /api/shopping {item, quantity?}  normalize -> merge quantity if the
                                         item already exists this week, else
                                         insert (categorized, source=manual).
  * DELETE /api/shopping/{item}?week=
  * POST   /api/shopping/toggle {item, week?}  flip checked; becoming CHECKED
                                         records the purchase (memory) and
                                         resets a matching staple's clock.
  * GET/POST/DELETE /api/staples         per-user restock-interval staples.

AUTH: every handler rides the ONE shared gate auth_service.current_user_or_401
(401, never 200). Week keys: POST/toggle/DELETE also accept ?week= (default =
current week) so callers — and tests — can target a specific week like GET.
``build-from-accepted`` (spec point 4) rides commit A's recipe_usage (b96555b).
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import auth_service, db
from app.models.recipe_usage import RecipeUsage
from app.models.recipes_db import Recipe
from app.models.shopping import (SOURCE_MANUAL, SOURCE_MEMORY, SOURCE_PLAN,
                                 SOURCE_STAPLE,
                                 ShoppingItem, Staple,
                                 due_memory_items, due_staples,
                                 record_purchase, staple_buy_reset)
from app.models.users import User
from app.services.shopping_text import combine_quantities, guess_category, normalize_item_name
from src.planner.weeks import current_week_key, week_to_monday

router = APIRouter(prefix="/api", tags=["shopping"])

WEEK_PATTERN = r"^\d{4}-W\d{1,2}$"   # same gate contract as the menu router


class ShoppingAdd(BaseModel):
    item: str = Field(min_length=1)
    quantity: str = ""


class ShoppingToggle(BaseModel):
    item: str = Field(min_length=1)
    week: str | None = Field(default=None, pattern=WEEK_PATTERN)


class StapleCreate(BaseModel):
    item: str = Field(min_length=1)
    interval_days: int = Field(ge=1)


class ItemOut(BaseModel):
    item: str
    quantity: str = ""
    category: str
    checked: int
    added_manually: int
    source: str


class StapleOut(BaseModel):
    item: str
    interval_days: int
    last_bought: str | None


def _week_or_422(week: str | None) -> str:
    week_key = week or current_week_key()
    try:
        week_to_monday(week_key)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"week is not a real ISO week: {week_key!r}") from None
    return week_key


def _rows(session, user_id: int, week_key: str) -> list[ShoppingItem]:
    return (session.query(ShoppingItem)
            .filter_by(user_id=user_id, week_key=week_key)
            .order_by(ShoppingItem.id).all())


def _inject_due(session, user_id: int, week_key: str) -> None:
    """Fresh-week injection: due staples first, then due habits, deduped."""
    existing = {r.item for r in _rows(session, user_id, week_key)}
    if existing:
        return                       # not a fresh week: never re-inject
    for st in due_staples(session, user_id):
        session.add(ShoppingItem(user_id=user_id, week_key=week_key,
                                 item=st.item, quantity="",
                                 category=guess_category(st.item),
                                 source=SOURCE_STAPLE))
        existing.add(st.item)
    for mem in due_memory_items(session, user_id):
        if mem.item in existing:     # staples entry wins on collision
            continue
        session.add(ShoppingItem(user_id=user_id, week_key=week_key,
                                 item=mem.item, quantity="",
                                 category=guess_category(mem.item),
                                 source=SOURCE_MEMORY))
    session.commit()


# ─── shopping list ────────────────────────────────────────────────────────────


@router.get("/shopping", response_model=list[ItemOut])
def get_shopping(request: Request,
                 week: str | None = Query(default=None, pattern=WEEK_PATTERN),
                 user: User = Depends(auth_service.current_user_or_401),
                 session=Depends(db.get_db)):
    """The user's list for the week (default: current), due items injected."""
    week_key = _week_or_422(week)
    _inject_due(session, user.user_id, week_key)
    return _rows(session, user.user_id, week_key)


@router.post("/shopping", response_model=ItemOut)
def add_shopping(payload: ShoppingAdd,
                 request: Request,
                 week: str | None = Query(default=None, pattern=WEEK_PATTERN),
                 user: User = Depends(auth_service.current_user_or_401),
                 session=Depends(db.get_db)):
    """Add manually; normalize + categorize + merge quantities (matapp GT-1e)."""
    week_key = _week_or_422(week)
    item = normalize_item_name(payload.item)
    if not item:
        raise HTTPException(status_code=400, detail="empty item after normalize")
    row = (session.query(ShoppingItem)
           .filter_by(user_id=user.user_id, week_key=week_key, item=item)
           .first())
    if row is not None:
        row.quantity = combine_quantities(row.quantity, payload.quantity)
    else:
        row = ShoppingItem(user_id=user.user_id, week_key=week_key, item=item,
                           quantity=payload.quantity,
                           category=guess_category(item),
                           added_manually=1, source=SOURCE_MANUAL)
        session.add(row)
    session.commit()
    return row


@router.delete("/shopping/{item}")
def remove_shopping(item: str,
                    request: Request,
                    week: str | None = Query(default=None, pattern=WEEK_PATTERN),
                    user: User = Depends(auth_service.current_user_or_401),
                    session=Depends(db.get_db)) -> dict:
    week_key = _week_or_422(week)
    key = normalize_item_name(item)
    deleted = (session.query(ShoppingItem)
               .filter_by(user_id=user.user_id, week_key=week_key, item=key)
               .delete())
    session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"item not on the list: {item}")
    return {"ok": True, "item": key, "week": week_key}


@router.post("/shopping/toggle", response_model=ItemOut)
def toggle_shopping(payload: ShoppingToggle,
                    request: Request,
                    user: User = Depends(auth_service.current_user_or_401),
                    session=Depends(db.get_db)):
    """Flip checked; checking = a PURCHASE (memory + staple reset, P2-a/P2-b)."""
    week_key = _week_or_422(payload.week)
    key = normalize_item_name(payload.item)
    row = (session.query(ShoppingItem)
           .filter_by(user_id=user.user_id, week_key=week_key, item=key)
           .first())
    if row is None:
        raise HTTPException(status_code=404, detail=f"item not on the list: {payload.item}")
    row.checked = 0 if row.checked else 1
    if row.checked:
        record_purchase(session, user.user_id, key)
        staple_buy_reset(session, user.user_id, key)
    session.commit()
    return row


# ─── build-from-accepted-plan (MC 10037 P1-b, spec point 4) ──────────────────


@router.post("/shopping/build")
def build_from_plan(request: Request,
                    week: str | None = Query(default=None, pattern=WEEK_PATTERN),
                    user: User = Depends(auth_service.current_user_or_401),
                    session=Depends(db.get_db)) -> dict:
    """Aggregate the ACCEPTED plan's ingredients into the week's list.

    ONE clock (recipe_usage is written only by POST /api/menu/accept): the
    week must have the user's accepted rows, else 404. Ingredients join back
    via dish title == Recipe.title (the accept records exactly what
    plan_menu chose). Upsert semantics: existing rows merge quantities (never
    duplicated, source kept), new rows are inserted source='plan'.
    """
    week_key = _week_or_422(week)
    usage = (session.query(RecipeUsage)
             .filter_by(user_id=user.user_id, week_key=week_key).all())
    if not usage:
        raise HTTPException(
            status_code=404,
            detail=f"no accepted plan for week {week_key}")

    titles = sorted({row.title for row in usage})
    recipes = (session.query(Recipe).filter(Recipe.title.in_(titles)).all())
    found = {r.title for r in recipes}
    missing = [t for t in titles if t not in found]
    if missing:
        raise HTTPException(status_code=409,
                            detail=f"accepted dishes missing from recipes table: {missing}")

    # Aggregate ingredients across the accepted dishes first (same item in
    # several dishes merges once, before touching the list).
    aggregated: dict[str, str] = {}
    for recipe in recipes:
        try:
            ingredients = json.loads(recipe.ingredients_json or "[]")
        except ValueError:
            continue
        for ing in ingredients:
            name = normalize_item_name(str(ing.get("name", "")))
            if not name:
                continue
            qty = ing.get("qty")
            quantity = f"{qty:g} {ing.get('unit', '')}".strip() if isinstance(qty, (int, float)) and qty else ""
            aggregated[name] = (combine_quantities(aggregated[name], quantity)
                                if name in aggregated else quantity)

    added = merged = 0
    for item, quantity in aggregated.items():
        row = (session.query(ShoppingItem)
               .filter_by(user_id=user.user_id, week_key=week_key, item=item)
               .first())
        if row is None:
            session.add(ShoppingItem(user_id=user.user_id, week_key=week_key,
                                     item=item, quantity=quantity,
                                     category=guess_category(item),
                                     source=SOURCE_PLAN))
            added += 1
        else:
            row.quantity = combine_quantities(row.quantity, quantity)
            merged += 1
    session.commit()
    return {"ok": True, "week": week_key, "dishes": len(recipes),
            "added": added, "merged": merged}


# ─── staples ──────────────────────────────────────────────────────────────────


@router.get("/staples", response_model=list[StapleOut])
def get_staples(request: Request,
                user: User = Depends(auth_service.current_user_or_401),
                session=Depends(db.get_db)):
    return (session.query(Staple).filter_by(user_id=user.user_id)
            .order_by(Staple.item).all())


@router.post("/staples", response_model=StapleOut)
def add_staple(payload: StapleCreate,
               request: Request,
               user: User = Depends(auth_service.current_user_or_401),
               session=Depends(db.get_db)):
    """Upsert (item, interval_days) — matapp staples, per-user relational."""
    key = normalize_item_name(payload.item)
    if not key:
        raise HTTPException(status_code=400, detail="empty item after normalize")
    row = (session.query(Staple)
           .filter_by(user_id=user.user_id, item=key).first())
    if row is None:
        row = Staple(user_id=user.user_id, item=key,
                     interval_days=payload.interval_days)
        session.add(row)
    else:
        row.interval_days = payload.interval_days
    session.commit()
    return row


@router.delete("/staples/{item}")
def remove_staple(item: str,
                  request: Request,
                  user: User = Depends(auth_service.current_user_or_401),
                  session=Depends(db.get_db)) -> dict:
    key = normalize_item_name(item)
    deleted = (session.query(Staple)
               .filter_by(user_id=user.user_id, item=key).delete())
    session.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"staple not found: {item}")
    return {"ok": True, "item": key}
