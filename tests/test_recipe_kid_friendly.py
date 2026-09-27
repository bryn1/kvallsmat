"""tests.test_recipe_kid_friendly — MC 1355.18 (T11) recipe-db fixtures.

Offline fixture tests: the starter seed marks the seven kid-typical dishes
``kid_friendly=1`` (0 elsewhere), and the scraper persists the flag from a
``file://`` source fixture. Local temp sqlite only — no network.
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import init_db

# src/recipes/seed.py + scraper.py import their sibling top-level
# (`from recipes.store import ...`) — the run_motor.py idiom (src on
# sys.path). Alias the ALREADY-IMPORTED package instead of adding src/ to
# sys.path: a second import path would redefine the ORM class on the shared
# Base and raise InvalidRequestError.
import src.recipes as _recipes_pkg  # noqa: E402
import src.recipes.store as _recipes_store  # noqa: E402
sys.modules.setdefault("recipes", _recipes_pkg)
sys.modules.setdefault("recipes.store", _recipes_store)

KID_TITLES = [
    "Köttbullar med gräddsås och potatis",
    "Pannkakor med sylt",
    "Korv stroganoff",
    "Tacopaj",
    "Köttfärssås och spagetti",
    "Pasta med tomaatsås och basilika",
    "Quesadillas med bönor",
]


def _tmp_session():
    import tempfile

    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return sessionmaker(bind=engine, autoflush=False)()


def test_seed_marks_kid_recipes():
    from src.recipes.seed import seed_starter
    from src.recipes.store import Recipe, c_rdb_list_all

    conn = _tmp_session()
    try:
        assert seed_starter(conn) > 0
        rows = {r.title: r.kid_friendly for r in c_rdb_list_all(conn)}
        for title in KID_TITLES:
            assert rows[title] == 1, f"{title} must be kid_friendly=1"
        # Every other seeded dish is 0 (fish/curry/lentil/adult-palate set).
        others = {t: v for t, v in rows.items() if t not in KID_TITLES}
        assert others and all(v == 0 for v in others.values())
        # Idempotent rerun: values unchanged.
        seed_starter(conn)
        rows2 = {r.title: r.kid_friendly for r in c_rdb_list_all(conn)}
        assert rows2 == rows
    finally:
        conn.close()


def test_scraper_persists_kid_friendly(tmp_path):
    from src.recipes.scraper import scrape_recipes
    from src.recipes.store import Recipe

    source = tmp_path / "recipes.json"
    source.write_text(json.dumps({"recipes": [
        {"title": "Pannkakor med sylt", "kid_friendly": 1,
         "ingredients": [{"name": "mjöl", "qty": 3, "unit": "dl"}]},
        {"title": "Grönsakssoppa med bröd", "kid_friendly": 0,
         "ingredients": [{"name": "rotfrukter", "qty": 600, "unit": "g"}]},
        # Absent flag normalises to 0 (same idiom as vegetarian).
        {"title": "Pasta carbonara",
         "ingredients": [{"name": "spagetti", "qty": 400, "unit": "g"}]},
    ]}), encoding="utf-8")

    conn = _tmp_session()
    try:
        written = scrape_recipes(conn, f"file://{source}")
        assert written == 3
        rows = {r.title: r for r in conn.query(Recipe).all()}
        assert rows["Pannkakor med sylt"].kid_friendly == 1
        assert rows["Grönsakssoppa med bröd"].kid_friendly == 0
        assert rows["Pasta carbonara"].kid_friendly == 0
    finally:
        conn.close()
