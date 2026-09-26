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

from config import PlannerConfig
from fetcher.grocer import pull_grocer
from fetcher.aggregate import aggregate
from normalizer.chain_mapper import normalize
from offers_db.store import upsert_week
from database import make_engine, init_db
from sqlalchemy.orm import sessionmaker


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
         now: datetime | None = None) -> int:
    """Run one full weekly ingest pass. Returns 0 on success.

    session: injectable httpx-like client (tests); default = real httpx client per pull.
    db_url:  sqlite URL where the normalized offers are written (M4 offers-db).
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
                continue
            normalized = normalize(g.chain or g.grocer_id, raw, week_key)
            if normalized:
                # adapter: C4 NormalizedOffer carries `price` (cents); M4 offers-db
                # column is `price_cents`. Rewrite the key at the single wiring point.
                rows = [dict(n, price_cents=n.pop("price")) for n in normalized]
                upsert_week(conn, rows, week_key)
        conn.commit()
    finally:
        conn.close()
    return 0
