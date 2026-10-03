"""app.models.recipe_rating — per-user dish rating, upsert on (user, title).

MC 10037 (PORT-PLAN P1-a): ports matapp's household-rating idea
(recipe_history kid1/kid2/adult_liked + rating) to ONE kvallsmat-native
relational table: rating 1..7 (validation is the router's pydantic boundary),
one row per user+title, re-rating overwrites (upsert), created_at stamped at
write time. Ratings are the fuel for a later preference pass — this card only
records them (matapp consumes them the same conservative way).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Session

from database import Base


class RecipeRating(Base):
    __tablename__ = "recipe_rating"

    rating_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False,
                     index=True)
    title = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)     # 1..7, validated at the router
    created_at = Column(DateTime, nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "title", name="uq_recipe_rating_user_title"),
    )


def upsert_rating(session: Session, user_id: int, title: str,
                  rating: int) -> RecipeRating:
    """Insert or overwrite the user's rating for this title (idempotent)."""
    row = (session.query(RecipeRating)
           .filter_by(user_id=user_id, title=title).first())
    if row is None:
        row = RecipeRating(user_id=user_id, title=title, rating=rating)
        session.add(row)
    else:
        row.rating = rating
        row.created_at = datetime.now(timezone.utc)
    session.commit()
    return row


def list_ratings(session: Session, user_id: int) -> list[RecipeRating]:
    return (session.query(RecipeRating)
            .filter_by(user_id=user_id)
            .order_by(RecipeRating.title)
            .all())
