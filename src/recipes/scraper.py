"""MODULE M7 — recipe-scraper (fills recipe-db M6).

REV6 CONTRACT C-RS (src/recipes/scraper.py): pulls recipes from a chosen source
into recipe-db, deduped on ``title``, via a source-agnostic adapter so the
specific source choice is config, not a rewrite. Mirrors REV4's C6 recipe-scraper
and the bibliotek ``on_page`` checkpoint idiom.

    def scrape_recipes(conn, source: str, limit: int = 0,
                       on_page: Callable[[list[Recipe]], None] | None = None) -> int

Boundary: ``list[Recipe]`` in -> recipe-db; returns count written.

SEMANTICS (per MC 253.3 title "additiv mot seed"): the scraper is ADDITIVE against
the M6 starter seed. Titles already present in recipe-db (e.g. seed entries) are
SKIPPED, never overwritten — seed stays authoritative. Only titles not yet in the
store are inserted, and titles are deduped within a source run. The count returned
is the number of rows NEWLY written.

NOTE ON THE DESIGN'S OPEN RESEARCH ITEM (never silently closed): the architecture
(REV6 §6/§9) leaves the specific scrapable recipe source UNCHOSEN/UNVERIFIED — that
is the researcher seat's (artemis) to resolve, and no real scrapable site is
verified on this host (N8: nothing points at an absent object). C-RS is therefore
source-agnostic: ``source`` selects an adapter by URL scheme. A concrete, real and
verifiable ``http[s]://`` adapter (JSON recipe document) and a ``file://`` adapter
are provided so the contract is executable end-to-end; pointing it at a specific
live site is a config change, gated separately by the tester.
"""
import json
import urllib.parse
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx
from sqlalchemy.orm import Session

from recipes.store import upsert_recipe, Recipe

PAGE_SIZE = 10


def _is_http(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _is_file(source: str) -> bool:
    return source.startswith("file://")


def _fetch_document(source: str) -> dict:
    """Fetch + parse a recipe-source JSON document. Returns {"recipes": [...]}.

    Raises on transport/parse failure for a *known* scheme so the caller can
    treat it as a failed source (fail-tolerant), matching the M2 fetcher idiom.
    """
    if _is_http(source):
        resp = httpx.get(source, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    if _is_file(source):
        path = urllib.parse.urlparse(source).path
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    raise ValueError(f"unsupported recipe source scheme: {source!r}")


def _normalize_spec(spec, source: str) -> Optional[dict]:
    """Map one raw source entry to a Recipe row dict, or None if malformed.

    Malformed entries (non-dict, missing title, non-string title) are dropped,
    not fatal — mirroring C2's drop-not-fail policy.
    """
    if not isinstance(spec, dict):
        return None
    title = spec.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    row = {
        "title": title.strip(),
        "category": _text(spec.get("category"), "husmanskost"),
        "servings": _int(spec.get("servings"), 4),
        "vegetarian": 1 if _int(spec.get("vegetarian"), 0) else 0,
        # MC 1355.18 (T11): same 0/1 normalisation idiom as vegetarian.
        "kid_friendly": 1 if _int(spec.get("kid_friendly"), 0) else 0,
        "budget_tier": _text(spec.get("budget_tier"), "mid"),
        "ingredients_json": json.dumps(spec.get("ingredients", []), ensure_ascii=False),
        "allergens_json": json.dumps(spec.get("allergens", []), ensure_ascii=False),
        "source_url": _text(spec.get("source_url"), ""),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return row


def _text(v, default: str) -> str:
    return v if isinstance(v, str) else default


def _int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _exists(conn: Session, title: str) -> bool:
    return conn.query(Recipe).filter_by(title=title).first() is not None


def scrape_recipes(conn: Session, source: str, limit: int = 0,
                   on_page: Optional[Callable[[list[Recipe]], None]] = None) -> int:
    """CONTRACT C-RS: scrape a recipe source into recipe-db; returns rows written."""
    if not (_is_http(source) or _is_file(source)):
        raise ValueError(f"unsupported recipe source scheme: {source!r}")

    try:
        doc = _fetch_document(source)
    except Exception:
        # Fail-tolerant on the DATA fetch path for a known scheme (M2 idiom):
        # a source that errors writes nothing and does not raise.
        return 0

    specs = doc.get("recipes", []) if isinstance(doc, dict) else []
    if limit:
        specs = specs[:limit]

    written = 0
    for i in range(0, len(specs), PAGE_SIZE):
        page_specs = specs[i:i + PAGE_SIZE]
        page_rows = []
        for spec in page_specs:
            row = _normalize_spec(spec, source)
            if row is None:
                continue                  # malformed entry dropped, not fatal
            if _exists(conn, row["title"]):
                continue                  # additive vs seed: never overwrite existing title
            upsert_recipe(conn, row)      # insert-only here (title already verified absent)
            written += 1
            page_rows.append(conn.query(Recipe).filter_by(title=row["title"]).first())
        if on_page and page_rows:
            on_page(page_rows)
    return written
