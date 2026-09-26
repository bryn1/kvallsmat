"""RED tests for M6 recipe-db (C-RDB). Run: python -m pytest tests/test_recipes_db.py"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from database import Base
from recipes.store import upsert_recipe, c_rdb_list_all, Recipe


def rec(title, **over):
    base = dict(category="husmanskost", servings=4, ingredients_json='[]',
                allergens_json='[]', vegetarian=0, budget_tier="mid",
                source_url="", created_at="2026-08-21T16:00:00Z")
    base.update(over)
    base["title"] = title
    return base


@pytest.fixture()
def conn():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_upsert_recipe_writes(conn):
    r = rec("Köttbullar")
    n = upsert_recipe(conn, r)
    assert n == 1
    allr = c_rdb_list_all(conn)
    assert len(allr) == 1
    assert allr[0].title == "Köttbullar"


def test_upsert_recipe_idempotent_on_unique_title(conn):
    upsert_recipe(conn, rec("Pannkakor", category="vegetarisk"))
    # same title -> update, not duplicate
    n = upsert_recipe(conn, rec("Pannkakor", servings=6))
    assert n == 1
    allr = c_rdb_list_all(conn)
    assert len(allr) == 1
    assert allr[0].servings == 6


def test_recipe_unique_title_constraint(conn):
    insp = inspect(conn.bind)
    uniques = [u["column_names"] for u in insp.get_unique_constraints("recipes")]
    assert ["title"] in uniques


def test_json_columns_roundtrip(conn):
    ing = [{"name": "mjölk", "qty": 4, "unit": "dl"}]
    al = ["mjölk", "gluten"]
    upsert_recipe(conn, rec("Tacopaj", ingredients_json=json.dumps(ing),
                            allergens_json=json.dumps(al), vegetarian=1))
    got = c_rdb_list_all(conn)[0]
    assert json.loads(got.ingredients_json) == ing
    assert json.loads(got.allergens_json) == al
    assert got.vegetarian == 1
