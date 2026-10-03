"""app.routers.plans — POST /api/menu/accept + recipe ratings (MC 10037 P1-a).

Split from app/routers/menu.py per the repo's size ceiling (menu.py stays the
GET/assembly owner, <400 lines); both new surfaces are thin HTTP wire-ups over
existing single implementations:

  * accept REUSES the one shared assembly ``menu._assemble_menu`` and RECOMPUTES
    the exact plan for the given seed — there is no second plan builder. It
    then writes the rotation clock (recipe_usage, replace-all per user+week).
  * rate upserts per-user ratings (recipe_rating), the conservative port of
    matapp's household-rating idea: this wave only records them.

Auth: every handler resolves the session cookie via the SAME dependency
``menu._current_user_or_401`` the menu GET uses — absent/invalid cookie is 401,
never 200 (gate-C6 line, one gate not two).
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import db
from app.models.recipe_rating import list_ratings, upsert_rating
from app.models.recipe_usage import replace_week_usage
from app.models.users import User
from app.optimizer.optimizer import DEFAULT_SEEDS
from app.routers.menu import (WEEK_PATTERN, _assemble_menu,
                              _current_user_or_401)
from src.planner.weeks import current_week_key

accept_router = APIRouter(prefix="/api/menu", tags=["menu"])
recipe_router = APIRouter(prefix="/api/recipe", tags=["recipe"])


class AcceptBody(BaseModel):
    seed: int
    week: str | None = None


@accept_router.post("/accept")
def accept_plan(body: AcceptBody,
                request: Request,
                user: User = Depends(_current_user_or_401),
                session=Depends(db.get_db)) -> dict:
    """Accept one of THIS week's three suggestions: recompute its exact plan,
    record the rotation usage (replace-all for user+week), return the dishes."""
    if body.week is not None and not re.fullmatch(WEEK_PATTERN, body.week):
        raise HTTPException(
            status_code=422,
            detail=f"week is not a well-formed ISO week key: {body.week!r}")
    week_key = body.week or current_week_key()
    menu = _assemble_menu(session, user, week_key)  # 422 on a fake week
    suggestion = next((s for s in menu.suggestions if s.seed == body.seed),
                      None)
    if suggestion is None:
        raise HTTPException(
            status_code=422,
            detail=f"seed {body.seed} is not one of the offered seeds "
                   f"{sorted(DEFAULT_SEEDS)}")
    dishes = [d.dish_id for d in suggestion.days]
    replace_week_usage(session, user.user_id, week_key, body.seed, dishes)
    return {"ok": True, "week_key": week_key, "dishes": dishes}


class RateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rating: int = Field(ge=1, le=7)  # matapp's 1..7 household scale


@recipe_router.post("/rate")
def rate_recipe(body: RateBody,
                request: Request,
                user: User = Depends(_current_user_or_401),
                session=Depends(db.get_db)) -> dict:
    """Upsert the authenticated user's rating for one dish title."""
    upsert_rating(session, user.user_id, body.title, body.rating)
    return {"ok": True, "title": body.title, "rating": body.rating}


@recipe_router.get("/ratings")
def get_ratings(request: Request,
                user: User = Depends(_current_user_or_401),
                session=Depends(db.get_db)) -> list[dict]:
    """The authenticated user's ratings, title-ordered."""
    return [{"title": r.title, "rating": r.rating,
             "created_at": r.created_at.isoformat()}
            for r in list_ratings(session, user.user_id)]
