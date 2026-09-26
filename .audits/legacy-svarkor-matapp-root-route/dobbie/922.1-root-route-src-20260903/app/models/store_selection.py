"""C5 — STORE-SELECTION module (the ONE new web-layer table).

Persists Alex' chosen stores on the motor's shared Base so C2 boot creates it
atomically alongside the motor's own tables (declared on src/database.py Base —
NOT a second engine, NOT a fork). Single concern: persist the chosen stores.

Store ids are read from PlannerConfig grocers (REV2 O1) at call time — never a
hardcoded second list — so the selection always reflects the motor's own config.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import Session

from database import Base            # motor shared Base (import BEFORE init_db FIX 2)
from config import PlannerConfig     # O1: source of store ids

MAX_SELECTED = 3


class StoreSelection(Base):
    __tablename__ = "store_selection"

    store_id = Column(String, primary_key=True)   # motor grocer id (O1 — never invented)
    selected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<StoreSelection {self.store_id}>"


def upsert_selection(session: Session, store_ids: list[str],
                     config: PlannerConfig | None = None) -> list[str]:
    """Replace-all selected stores with *store_ids*, capped at 3.

    Uses *config* (default a stock PlannerConfig) purely as validation source —
    the O1 pin, never a second hardcoded store list. Unknown store_id raises
    ValueError. Returns the actually-selected store_ids (post cap).
    """
    valid = {g.grocer_id for g in (config or PlannerConfig()).grocers}
    bad = [sid for sid in store_ids if sid not in valid]
    if bad:
        raise ValueError(f"unknown store_id(s): {bad}")

    keep = store_ids[:MAX_SELECTED]
    # replace-all: delete every existing row, then insert fresh (cap enforced)
    session.query(StoreSelection).delete()
    now = datetime.now(timezone.utc)
    for sid in keep:
        session.add(StoreSelection(store_id=sid, selected_at=now))
    session.commit()
    return keep


def list_selected(session: Session) -> list[StoreSelection]:
    """Return the selected stores in insertion order."""
    return session.query(StoreSelection).order_by(StoreSelection.selected_at).all()
