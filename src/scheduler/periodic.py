"""M1 scheduler.periodic — CONTRACT C1 (REV6 §2, module M1).

Drives the weekly ingest pass:
  choose_week -> schedule_run -> (for each grocer) pull_grocer -> aggregate
              -> normalize (C4) -> offers_db.upsert_week (M4)

``choose_week`` and ``schedule_run`` are PURE and deterministic. ``main`` wires the whole
line end-to-end and returns process exit code 0 on success. It never raises for a single
grocer's feed problems (the fetcher already degrades to an empty feed).
"""
from __future__ import annotations

from datetime import datetime
import logging

# MC 1355.5: the repo root is on sys.path in BOTH contexts (run_motor.py runs from
# the root; the web app / tests put the root on path), so the ``src.`` package
# spelling resolves everywhere. ``database`` is a repo-root module either way.
from src.config import PlannerConfig
from src.fetcher.adapters.tjek import pull_store_scoped
from src.fetcher.grocer import pull_grocer
from src.fetcher.aggregate import aggregate
from src.normalizer.chain_mapper import normalize
from src.offers_db.store import upsert_week
from database import make_engine, init_db
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# T10b §3 Population: the storeflyer endpoint returns the per-store leaflet
# metadata whose ``name`` is the store's Tjek catalog label (T10a §2, VERIFIED).
_WILLYS_STOREFLYER = "https://www.willys.se/axfood/rest/v2/storeflyer/"


def choose_week(cfg, now: datetime | None = None) -> str:
    """ISO week key "YYYY-Www" of the running/configured week (CONTRACT C1)."""
    if cfg and cfg.week_override:
        return cfg.week_override
    now = now or datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def schedule_run(cfg) -> list[str]:
    """Ordered grocer_ids to pull for the week (CONTRACT C1)."""
    return [g.grocer_id for g in cfg.grocers]


def main(cfg: PlannerConfig | None = None, session=None, db_url="sqlite:///kvallsmat.db",
         now: datetime | None = None, resolved_stores=None) -> int:
    """Run one full weekly ingest pass. Returns 0 on success.

    session: injectable httpx-like client (tests); default = real httpx client per pull.
    db_url:  sqlite URL where the normalized offers are written (M4 offers-db).
    resolved_stores: optional list of persisted profile ``resolved_stores`` JSON
        objects (T10b §3 Population). When given, a Willys store-scoped ingest
        pass runs after the chain-level upserts (MC 1355.17 / T10f cycle 1);
        absent/empty keeps the pass a no-op.
    """
    cfg = cfg or PlannerConfig()
    week_key = choose_week(cfg, now=now)
    engine = make_engine(db_url)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    per_grocer = {}
    for g in cfg.grocers:
        per_grocer[g.grocer_id] = pull_grocer(g, week_key, session=session)

    merged = aggregate(per_grocer.values())
    conn = Session()
    try:
        for g in cfg.grocers:
            raw = per_grocer[g.grocer_id]
            if not raw["entries"]:
                # MC 1355.7 (T5 attack 2): a grocer yielding ZERO entries is a
                # silent total failure (adapter breakage degrades to an empty
                # feed, never an exception) — it must be LOUD, not green-silent.
                logger.warning(
                    "grocer %s yielded 0 offers for %s — feed may be broken; "
                    "menus degrade to recipe-only for its items",
                    g.grocer_id, week_key)
                continue
            normalized = normalize(g.chain or g.grocer_id, raw, week_key)
            if normalized:
                # adapter: C4 NormalizedOffer carries `price` (cents); M4 offers-db
                # column is `price_cents`. Rewrite the key at the single wiring point.
                rows = [dict(n, price_cents=n.pop("price")) for n in normalized]
                upsert_week(conn, rows, week_key)
        if resolved_stores:
            written = run_store_scoped_ingest(
                conn, week_key, resolved_stores, session=session, cfg=cfg)
            if written:
                logger.info("store-scoped ingest wrote %d willys rows for %s",
                            written, week_key)
        conn.commit()
    finally:
        conn.close()
    return 0


# ---------------------------------------------------------------------------
# Willys store-scoped ingest (T10b §3 Population — MC 1355.17, T10f cycle 1)
# ---------------------------------------------------------------------------

def collect_resolved_willys(resolved_list) -> list[dict]:
    """Distinct resolved Willys stores across all saved profiles (T10b §3).

    ``resolved_list`` holds the persisted ``resolved_stores`` JSON objects of
    every profile that has one. Only chains with status ``ok`` contribute; a
    store is deduped on its store_id (several users share the same store).
    """
    seen: set[str] = set()
    out: list[dict] = []
    for resolved in resolved_list or []:
        entry = ((resolved or {}).get("chains") or {}).get("willys") or {}
        if entry.get("status") != "ok":
            continue
        for store in entry.get("stores") or []:
            sid = str(store.get("store_id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(store)
    return out


def _willys_catalog_label(store_id: str, client) -> str | None:
    """Tjek catalog label for a Willys store via the storeflyer endpoint.

    T10b §3: the store list carries ``flyerURL``/``storeId`` and the storeflyer
    endpoint returns the catalog name — that name is the Tjek label the
    store-scoped pull matches on. None on any failure (caller falls back to
    the store's own name).
    """
    import json

    from src.fetcher.adapters._common import get_text

    text = get_text(client, f"{_WILLYS_STOREFLYER}{store_id}", {})
    if text is None:
        return None
    try:
        return json.loads(text).get("name") or None
    except ValueError:
        return None


def run_store_scoped_ingest(conn, week_key: str, resolved_list,
                            session=None, cfg: PlannerConfig | None = None) -> int:
    """Willys store-scoped ingest pass (T10b §3 Population, MC 1355.17).

    The PRODUCTION caller of the Tjek adapter's ``pull_store_scoped``: each
    resolved Willys store is joined to its Tjek catalog label — storeflyer
    endpoint first (the design's flyerURL store-number join), the store's own
    name string as fallback — then the store-scoped feed is pulled, normalized
    and upserted WITH ``store_id`` (RULE 1: prefixed external ids, so a
    store-scoped row never overwrites a chain-level NULL row). Fail-tolerant
    per store: a failed label join or feed is logged and skipped, never fatal.
    Returns rows written.
    """
    import httpx

    stores = collect_resolved_willys(resolved_list)
    if not stores:
        return 0
    cfg = cfg or PlannerConfig()
    willys_cfg = next((g for g in cfg.grocers if g.grocer_id == "willys"), None)
    if willys_cfg is None:
        logger.warning("no willys grocer configured — store-scoped ingest skipped")
        return 0
    own = session is None
    client = session if session is not None else httpx.Client()
    written = 0
    try:
        for store in stores:
            sid = str(store["store_id"])
            label = _willys_catalog_label(sid, client) or store.get("store_name") or ""
            if not label:
                logger.warning("willys store %s has no label — skipped", sid)
                continue
            try:
                raw = pull_store_scoped(willys_cfg, week_key, sid, label,
                                        session=client)
            except Exception:  # fail-tolerant per store, never fatal
                logger.warning("store-scoped pull failed for willys store %s",
                               sid, exc_info=True)
                continue
            if not raw["entries"]:
                continue  # pull_store_scoped already logged the unmatched case
            normalized = normalize("willys", raw, week_key)
            # Wiring point: the store scope rides the row into offers-db (the
            # normalizer is store-agnostic, like the price_cents rewrite above).
            rows = [dict(n, price_cents=n.pop("price"), store_id=sid)
                    for n in normalized]
            written += upsert_week(conn, rows, week_key)
    finally:
        if own and hasattr(client, "close"):
            client.close()
    return written
