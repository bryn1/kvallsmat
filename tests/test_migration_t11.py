"""tests.test_migration_t11 — MC 1355.18 (T11) guarded-ALTER migration fixture.

Boots ``ensure_columns`` against a LEGACY database (pre-T11 schema: no
num_children / prefer_kid_friendly / kid_friendly) and asserts the three
columns are added, idempotently. Offline — a local file sqlite only.
"""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text


def _legacy_schema(engine) -> None:
    """Create the pre-T11 profile/recipes tables (raw SQL, no new columns)."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE profile ("
            " profile_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL UNIQUE,"
            " persons INTEGER NOT NULL,"
            " meal_days INTEGER NOT NULL,"
            " kron_budget INTEGER,"
            " selected_stores VARCHAR,"
            " postal_code VARCHAR,"
            " resolved_stores TEXT,"
            " updated_at DATETIME)"))
        conn.execute(text(
            "CREATE TABLE recipes ("
            " recipe_id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title VARCHAR NOT NULL UNIQUE,"
            " category VARCHAR,"
            " servings INTEGER,"
            " ingredients_json TEXT,"
            " allergens_json TEXT,"
            " vegetarian INTEGER,"
            " budget_tier VARCHAR,"
            " source_url VARCHAR,"
            " created_at VARCHAR)"))


def _columns(engine, table) -> set:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_ensure_columns_adds_t11_columns_on_legacy_db():
    from app.db import ensure_columns

    engine = create_engine("sqlite:///:memory:")
    _legacy_schema(engine)

    assert "num_children" not in _columns(engine, "profile")
    assert "prefer_kid_friendly" not in _columns(engine, "profile")
    assert "kid_friendly" not in _columns(engine, "recipes")

    ensure_columns(engine)

    assert "num_children" in _columns(engine, "profile")
    assert "prefer_kid_friendly" in _columns(engine, "profile")
    assert "kid_friendly" in _columns(engine, "recipes")

    # Idempotent: a second pass must be a no-op (no duplicate-column error).
    ensure_columns(engine)
    assert "kid_friendly" in _columns(engine, "recipes")
