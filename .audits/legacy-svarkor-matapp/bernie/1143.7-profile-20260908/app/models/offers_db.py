"""PHASE 2 (T1) db-foundation — OFFER model on the shared database.Base, WITH reference price.

Stänger closure-gap 1 (PHASE0.md §A / PHASE0-research Q4): the POC offer schema saved
ONLY ``price_cents`` — the reference/regular price was dropped (VERIFIED grep 0 träffar,
DA verdict §1). This model carries the seller's advertised regular (non-sale) price and
the implied per-unit savings, so Phase 4 offer-ingest can persist them and Phase 6
optimizer can apply the >=50%-extrapris ratio rule.

Keeps the POC's UNIQUE (grocer_id, external_id, week_key) natural key and week-key
index exactly (REV6 CONTRACT C5 / C-OW shape) — this is the NEW-SCHEMA home of the
same offers table, not a fork.

Imports the shared Base BEFORE init_db (fix-2 idiom, see app/db.py boot()).
"""
from __future__ import annotations

from sqlalchemy import Column, Index, Integer, String, UniqueConstraint

from database import Base  # shared Base (import BEFORE init_db — fix-2 idiom)


class Offer(Base):
    __tablename__ = "offers"

    offer_id = Column(Integer, primary_key=True, autoincrement=True)
    grocer_id = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    week_key = Column(String, nullable=False)
    name = Column(String)
    price_cents = Column(Integer)            # the sale/current price (existing column)
    regular_price_cents = Column(Integer)    # reference price — NEW (closure-gap 1)
    savings_cents = Column(Integer)          # regular - current — NEW (closure-gap 1)
    unit = Column(String)
    valid_from = Column(String)              # ISO 'YYYY-MM-DD' (week-scoped)
    valid_to = Column(String)

    __table_args__ = (
        UniqueConstraint("grocer_id", "external_id", "week_key", name="uq_offer"),
        Index("ix_offers_week_grocer", "week_key", "grocer_id"),
    )

    def __repr__(self):
        return f"<Offer {self.grocer_id}/{self.external_id} {self.week_key}>"
