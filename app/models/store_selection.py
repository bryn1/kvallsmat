"""app.models.store_selection — STORE-SELECTION model (ported from the deployed
hosting copy, MC 1355.3 T3; origin: hosting/apps/matapp app/models/store_selection.py).

Persists the chosen stores on the shared ``database.Base`` so app.db boot()
creates it atomically alongside users/profile/offers (declared on the root
database.Base — NOT a second engine, NOT a fork). Single concern: persist the
chosen stores.

Store ids are read from PlannerConfig grocers (REV2 O1) at call time — never a
hardcoded second list — so the selection always reflects the motor's own config.

Adaptation to this tree (MC 1355.3): ``Base`` comes from the root ``database``
module (the SAME Base app.models.users/profile use) and PlannerConfig from the
in-tree ``src.config`` — the hosting copy's motor-repo sys.path seam is not
needed here. ``valid_store_ids`` is shared by the stores router AND the profile
router (audit P1-2 fix) so there is exactly ONE validation source.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import Session

from database import Base            # shared Base (import BEFORE init_db FIX 2)
from src.config import PlannerConfig  # O1: source of store ids

MAX_SELECTED = 3


class StoreSelection(Base):
    __tablename__ = "store_selection"

    store_id = Column(String, primary_key=True)   # motor grocer id (O1 — never invented)
    selected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<StoreSelection {self.store_id}>"


def valid_store_ids(config: PlannerConfig | None = None) -> set[str]:
    """Return the set of store ids the given (or stock) PlannerConfig knows (O1)."""
    return {g.grocer_id for g in (config or PlannerConfig()).grocers}


def upsert_selection(session: Session, store_ids: list[str],
                     config: PlannerConfig | None = None) -> list[str]:
    """Replace-all selected stores with *store_ids*, capped at 3.

    Uses *config* (default a stock PlannerConfig) purely as validation source —
    the O1 pin, never a second hardcoded store list. Unknown store_id raises
    ValueError. Returns the actually-selected store_ids (post cap).
    """
    valid = valid_store_ids(config)
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
