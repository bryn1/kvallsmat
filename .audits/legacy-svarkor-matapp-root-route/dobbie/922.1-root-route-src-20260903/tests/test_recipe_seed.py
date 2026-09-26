"""RED tests for M6 starter seed (C-RDB seed_starter). Run: python -m pytest tests/test_recipe_seed.py"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from recipes.store import c_rdb_list_all
from recipes.seed import seed_starter, STARTER_ROSTER


@pytest.fixture()
def conn():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng)
    s = S()
    yield s
    s.close()


def test_seed_starter_populates(conn):
    n = seed_starter(conn)
    assert 15 <= n <= 25
    assert len(c_rdb_list_all(conn)) == n


def test_seed_starter_idempotent_rerun(conn):
    first = seed_starter(conn)
    second = seed_starter(conn)
    assert second == 0          # nothing new on rerun
    assert len(c_rdb_list_all(conn)) == first  # no duplication


def test_seed_titles_unique(conn):
    seed_starter(conn)
    titles = [r.title for r in c_rdb_list_all(conn)]
    assert len(titles) == len(set(titles))


def test_seed_recipes_have_required_fields(conn):
    seed_starter(conn)
    for r in c_rdb_list_all(conn):
        assert r.title
        assert r.servings > 0
        assert r.vegetarian in (0, 1)
        assert r.budget_tier in ("budget", "mid", "premium")
        assert r.created_at
