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
    week_key), existing rows are updated, not duplicated. Returns rows written
    (updated + inserted count). ``week_key`` is honored per-row if present on the
    dict, else filled from the argument.
    """
    written = 0
    for off in offers:
        row = dict(off)
        row.setdefault("week_key", week_key)
        key = {
            "grocer_id": row["grocer_id"],
            "external_id": row["external_id"],
            "week_key": row["week_key"],
        }
        existing = conn.query(Offer).filter_by(**key).first()
        if existing is None:
            conn.add(Offer(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)
        written += 1
    conn.commit()
    return written


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
