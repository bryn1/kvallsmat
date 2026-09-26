"""RED tests for M7 recipe-scraper (C-RS) — source-agnostic, additive, deduped on title.

Run: python3 -m pytest tests/test_recipe_scraper.py
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from recipes.store import c_rdb_list_all, upsert_recipe
from recipes.seed import seed_starter
from recipes import scraper


@pytest.fixture
def conn():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    S = sessionmaker(bind=eng)
    s = S()
    yield s
    s.close()


def write_doc(tmp_path, recipes):
    """Write a recipe-source JSON document to a temp file and return its file:// URL."""
    p = tmp_path / "source.json"
    p.write_text(json.dumps({"recipes": recipes}), encoding="utf-8")
    return p.as_uri()


def spec(title, **over):
    base = {
        "title": title, "category": "husmanskost", "servings": 4,
        "vegetarian": 0, "budget_tier": "mid",
        "ingredients": [{"name": "mjöl", "qty": 3, "unit": "dl"}],
        "allergens": [], "source_url": "",
    }
    base.update(over)
    return base


def test_scrape_file_source_writes(tmp_path, conn):
    src = write_doc(tmp_path, [spec("Apelsinpannkaka"), spec("Raggmunk")])
    n = scraper.scrape_recipes(conn, src)
    assert n == 2
    titles = {r.title for r in c_rdb_list_all(conn)}
    assert titles == {"Apelsinpannkaka", "Raggmunk"}


def test_scrape_is_additive_against_seed(tmp_path, conn):
    # Seed first (M6 starter roster).
    seed_starter(conn)
    before = {r.title for r in c_rdb_list_all(conn)}
    # Source reuses a seed title with DIFFERENT values + adds new ones.
    src = write_doc(tmp_path, [
        spec("Köttbullar med gräddsås och potatis", servings=99, budget_tier="premium"),
        spec("Brandny rätt"),
    ])
    n = scraper.scrape_recipes(conn, src)
    after = {r.title for r in c_rdb_list_all(conn)}
    # Only the NEW title is written; the seed title is NOT overwritten.
    assert n == 1
    assert after == before | {"Brandny rätt"}
    seed_row = [r for r in c_rdb_list_all(conn) if r.title == "Köttbullar med gräddsås och potatis"][0]
    assert seed_row.servings == 4          # original seed value preserved
    assert seed_row.budget_tier == "budget"


def test_scrape_dedupes_titles_within_source(tmp_path, conn):
    src = write_doc(tmp_path, [spec("Dubbel"), spec("Dubbel"), spec("Enkel")])
    n = scraper.scrape_recipes(conn, src)
    assert n == 2
    assert len(c_rdb_list_all(conn)) == 2


def test_scrape_limit_caps_written(tmp_path, conn):
    src = write_doc(tmp_path, [spec(f"Rätt {i}") for i in range(5)])
    n = scraper.scrape_recipes(conn, src, limit=2)
    assert n == 2
    assert len(c_rdb_list_all(conn)) == 2


def test_scrape_on_page_checkpoint_invoked(tmp_path, conn):
    src = write_doc(tmp_path, [spec(f"Rätt {i}") for i in range(4)])
    calls = []
    scraper.scrape_recipes(conn, src, limit=4, on_page=lambda page: calls.append(page))
    # One checkpoint callback per page emitted; every emitted page is non-empty.
    assert calls and all(len(p) >= 1 for p in calls)


def test_scrape_http_source(tmp_path, conn):
    """The http:// adapter pulls a real recipe JSON document from a live local server."""
    import json as _json
    import http.server, socketserver, threading
    body = _json.dumps({"recipes": [spec("HTTP-rätt", category="fest", servings=2)]}).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/recipes.json"
        n = scraper.scrape_recipes(conn, url)
        assert n == 1
        got = c_rdb_list_all(conn)
        assert [r.title for r in got] == ["HTTP-rätt"]
        assert got[0].category == "fest"
    finally:
        srv.shutdown()
        srv.server_close()


def test_scrape_unknown_scheme_raises(tmp_path, conn):
    with pytest.raises(ValueError):
        scraper.scrape_recipes(conn, "gopher://does-not-exist/recipes")


def test_scrape_source_error_is_fail_tolerant(tmp_path, conn):
    # A file:// URL that does not exist -> returns 0, does not raise.
    missing = (tmp_path / "nope.json").as_uri()
    n = scraper.scrape_recipes(conn, missing)
    assert n == 0
    assert c_rdb_list_all(conn) == []


def test_scrape_malformed_entries_dropped_not_fatal(tmp_path, conn):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"recipes": [
        spec("Bra rätt"), {"title": None}, "notadict", {"ingredients": []},
    ]}), encoding="utf-8")
    n = scraper.scrape_recipes(conn, p.as_uri())
    assert n == 1
    assert [r.title for r in c_rdb_list_all(conn)] == ["Bra rätt"]
