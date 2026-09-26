"""C4 — menu router for the web-api module (484.3 T3).

The ONLY correct wiring of the motor's plan_menu (C6) to HTTP:

  offers = list_offers_in_week(session, week)     # C-OW
  recipes = c_rdb_list_all(session)               # C-RDB
  family = FamilyPrefs(meal_days, persons, vegetarian, allergens, budget_tier)
  plan = plan_menu(week, offers, recipes, family, seed or 1234)
  return plan.json()                              # Plan is a dict subclass

NO business logic lives in this router — it is a thin passthrough of validated
params to the motor's planner. Every query parameter is pydantic-validated, so
out-of-range values are rejected with 422 before reaching the motor.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from offers_db.store import list_offers_in_week
from planner.menu import FamilyPrefs, plan_menu
from recipes.store import c_rdb_list_all

router = APIRouter(prefix="/api/menu", tags=["menu"])

DEFAULT_SEED = 1234


class MenuQuery(BaseModel):
    week: str = Field(
        ...,
        pattern=r"^\d{4}-W\d{1,2}$",
        description="ISO-8601 week key, e.g. '2026-W34'",
    )
    meal_days: int = Field(1, ge=1, le=14, description="antal middagar")
    persons: int = Field(1, ge=1, le=10, description="personer")
    vegetarian: bool = False
    budget_tier: str | None = Field(None, pattern="^(budget|mid|premium)$")
    allergens: list[str] | None = Field(
        default=None, description="allergen tags to exclude"
    )
    seed: int = DEFAULT_SEED


@router.get("")
def get_menu(q: MenuQuery = Depends(), session: Session = Depends(get_db)) -> dict:
    offers = list_offers_in_week(session, q.week)
    recipes = c_rdb_list_all(session)
    family = FamilyPrefs(
        meal_days=q.meal_days,
        persons=q.persons,
        vegetarian=q.vegetarian,
        allergens=tuple(q.allergens or ()),
        budget_tier=q.budget_tier,
    )
    plan = plan_menu(q.week, offers, recipes, family, seed=q.seed)
    return plan.json() if hasattr(plan, "json") else dict(plan)
