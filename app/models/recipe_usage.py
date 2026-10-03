"""app.models.recipe_usage — one accepted-plan record per user, week and dish.

MC 10037 (PORT-PLAN P1-a): the single CLOCK of the rotation feature. A row is
written ONLY by POST /api/menu/accept (what the household actually chose) —
never at plan time (matapp's two-clock mess, GT-5rz, is deliberately not
ported). The 42-day no-repeat window itself is applied in the menu router;
this module is pure persistence (no clock math, no web).

matapp ports recipe_history's role, kvallsmat-native and relational: one row
per (user, dish, week) carrying the seed the plan was computed with.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from database import Base


class RecipeUsage(Base):
    __tablename__ = "recipe_usage"

    usage_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False,
                     index=True)
    title = Column(String, nullable=False)
    week_key = Column(String, nullable=False)   # the week the dish was planned FOR
    seed = Column(Integer, nullable=False)       # seed the accepted plan used
    recorded_at = Column(DateTime, nullable=False,
                         default=lambda: datetime.now(timezone.utc))


def list_usage(session: Session, user_id: int) -> list[RecipeUsage]:
    """All usage rows for one user, newest accept first in INSERTION order
    (the router owns the window math)."""
    return (session.query(RecipeUsage)
            .filter_by(user_id=user_id)
            .order_by(RecipeUsage.usage_id)
            .all())


def replace_week_usage(session: Session, user_id: int, week_key: str,
                       seed: int, titles: list[str]) -> int:
    """Replace-all the user's usage rows for (user_id, week_key) (idempotent
    accept: re-accepting a week rewrites, never duplicates). Returns rows kept.
    """
    (session.query(RecipeUsage)
     .filter_by(user_id=user_id, week_key=week_key)
     .delete(synchronize_session=False))
    for title in titles:
        session.add(RecipeUsage(user_id=user_id, week_key=week_key,
                                seed=seed, title=title))
    session.commit()
    return len(titles)
