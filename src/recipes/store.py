"""MODULE M6 — recipe-db (persistence).

The SINGLE in-project store of the recipe set that planner C6 consumes. Owns the
Recipe schema and idempotent seeding. Implements REV6 CONTRACT C-RDB
(src/recipes/store.py). This replaces the phantom ``src/131/RecipeEngineCours`` as the
object a builder can actually find and read (N8).

Recipe-db is family- and offer-agnostic (N5) — no promo/family semantics here.
"""
import json
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import Session

from database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    recipe_id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False, unique=True)  # idempotent upsert key
    category = Column(String)
    servings = Column(Integer)
    ingredients_json = Column(Text)
    allergens_json = Column(Text)
    vegetarian = Column(Integer, default=0)  # 0/1
    # MC 1355.18 (T11): 0/1 barnvänligt. Declared on the model so create_all on
    # a FRESH database includes it (the guarded ALTER only covers existing DBs).
    # The guarded ALTER adds no DEFAULT: existing rows read NULL — treat as 0.
    kid_friendly = Column(Integer, default=0)  # 0/1
    budget_tier = Column(String)  # 'budget'|'mid'|'premium'
    source_url = Column(String, default="")
    created_at = Column(String)  # ISO UTC

    def __repr__(self):
        return f"<Recipe {self.title}>"


def upsert_recipe(conn: Session, r: dict) -> int:
    """CONTRACT C-RDB: idempotent upsert on UNIQUE title. Returns rows written."""
    key = {"title": r["title"]}
    existing = conn.query(Recipe).filter_by(**key).first()
    if existing is None:
        conn.add(Recipe(**r))
    else:
        for k, v in r.items():
            setattr(existing, k, v)
    conn.commit()
    return 1


def c_rdb_list_all(conn: Session) -> list[Recipe]:
    """CONTRACT C-RDB: the C6 recipe input seam — returns the whole recipe set."""
    return conn.query(Recipe).order_by(Recipe.title).all()
