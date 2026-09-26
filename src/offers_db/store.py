"""MODULE M4 — offers-db (persistence).

Stores the week's in-week offers idempotently and exposes keyed reads for the planner.
Implements REV6 CONTRACT C5 / C-OW (src/offers_db/store.py).

The Offers table carries a UNIQUE (grocer_id, external_id, week_key) constraint (N2)
and a (week_key, grocer_id) index for C-OW lookups. No filter logic lives here —
the running-week predicate is owned entirely by C4 (normalizer). Family/consume
semantics are out of scope for this module (N5).

MC 1355.5: this is the SINGLE canonical definition of the ``offers`` table. The
web layer's former duplicate (app/models/offers_db.py) is now a re-export shim —
two mappings of one tablename on the shared Base raise InvalidRequestError the
moment the menu router imports this module. The reference-price columns
(closure-gap 1) live here too, so the web schema is unchanged.
"""
from sqlalchemy import Column, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Session

from database import Base


class Offer(Base):
    __tablename__ = "offers"

    offer_id = Column(Integer, primary_key=True, autoincrement=True)
    grocer_id = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    week_key = Column(String, nullable=False)
    # MC 1355.16 (T10b §3): NULL = chain-level, valid everywhere (Lidl by
    # design; Coop until the dke path is captured). Store-scoped rows are
    # identity-distinct from chain-level rows — see upsert_week below.
    store_id = Column(String, nullable=True)
    name = Column(String)
    price_cents = Column(Integer)
    regular_price_cents = Column(Integer)  # reference price — closure-gap 1
    savings_cents = Column(Integer)        # regular - current — closure-gap 1
    unit = Column(String)
    valid_from = Column(String)  # ISO 'YYYY-MM-DD' (week-scoped, kept as string per REV6)
    valid_to = Column(String)

    __table_args__ = (
        UniqueConstraint("grocer_id", "external_id", "week_key", name="uq_offer"),
        Index("ix_offers_week_grocer", "week_key", "grocer_id"),
    )

    def __repr__(self):
        return f"<Offer {self.grocer_id}/{self.external_id} {self.week_key}>"


def upsert_week(conn: Session, offers: list[dict], week_key: str) -> int:
    """CONTRACT C5: write the week's in-week offers idempotently.

    Idempotent per N2: matching on the natural UNIQUE (grocer_id, external_id,
    week_key) PLUS the store scope, existing rows are updated, not
    duplicated. Returns rows written (updated + inserted count).
    ``week_key`` is honored per-row if present on the dict, else filled from
    the argument.

    MC 1355.16 (T10b §3): the match key gains ``store_id or ""`` — a
    store-scoped row never matches (and never overwrites) a chain-level
    ``store_id IS NULL`` row. RULE 1 (prefixing store-scoped external ids as
    ``"{store_id}:{hotspot_id}"`` at ingest, see the Tjek adapter) is the ONLY
    sanctioned ingest path for store-scoped rows; a payload that reuses a bare
    external id with a store-scoped store_id fails LOUD below (ValueError) —
    it is never silently merged into the chain-level row.
    """
    written = 0
    for off in offers:
        row = dict(off)
        row.setdefault("week_key", week_key)
        store_id = row.get("store_id") or None
        key = {
            "grocer_id": row["grocer_id"],
            "external_id": row["external_id"],
            "week_key": row["week_key"],
        }
        existing = _match(conn, key, store_id)
        if existing is None:
            if store_id is not None:
                _guard_bare_id_reuse(conn, key, store_id)
            conn.add(Offer(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)
        written += 1
    conn.commit()
    return written


def _match(conn: Session, key: dict, store_id: str | None):
    """Find the existing row for the match key INCLUDING the store scope."""
    query = conn.query(Offer).filter_by(**key)
    if store_id is None:
        return query.filter(Offer.store_id.is_(None)).first()
    return query.filter(Offer.store_id == store_id).first()


def _guard_bare_id_reuse(conn: Session, key: dict, store_id: str) -> None:
    """Fail LOUD when a store-scoped write reuses a bare external id (T10d N1).

    The UNIQUE constraint is (grocer_id, external_id, week_key), so such an
    insert would hit uq_offer as an IntegrityError. Rule 1 (prefixing) is the
    only sanctioned ingest path — a bare-id reappearance is a bug and must be
    loud, never a silent merge or retraction of the chain-level row.
    """
    clash = conn.query(Offer).filter_by(**key).first()
    if clash is not None:
        raise ValueError(
            "store-scoped offer reuses bare external_id "
            f"{key['external_id']!r} for {key['grocer_id']!r} "
            f"{key['week_key']!r} (store_id={store_id!r}) — rule 1 violated: "
            "store-scoped external ids must be prefixed at ingest")


def list_offers_in_week(conn: Session, week_key: str) -> list[Offer]:
    """CONTRACT C-OW: keyed, week-scoped read of offers. NO re-filter happens here —
    C4 owns the running-week predicate (N4); this is a plain keyed lookup.
    """
    return (
        conn.query(Offer)
        .filter(Offer.week_key == week_key)
        .order_by(Offer.grocer_id, Offer.external_id)
        .all()
    )
