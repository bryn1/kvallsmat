"""PHASE 2 (T1) db-foundation — PROFILE model on the shared database.Base.

Declares the ``profile`` table on the shared Base (POC fix-2 idiom: import BEFORE
init_db, see app/db.py boot()).

Single concern (Phase 5 T4 will build /api/profile on it): one row per user holding
Alex' menu preferences. Fields follow PHASE0-map.md §A / plan Phase 5:
  * persons        — number of people to cook for
  * meal_days      — how many days the plan must cover
  * kron_budget    — kronor budget per week (the "kron-budget" gate in Phase 5)
  * selected_stores— up to 3 chosen store ids (reuses the store_selection MAX=3 rule)
A foreign key to users.user_id ties the profile to the authenticated account
(Phase 5 requires the profile be stored against an authenticated session).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base  # shared Base (import BEFORE init_db — fix-2 idiom)

MAX_SELECTED_STORES = 3  # mirrors the POC store_selection cap (PHASE0-map.md §A)


class Profile(Base):
    __tablename__ = "profile"

    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)
    persons = Column(Integer, nullable=False, default=2)
    meal_days = Column(Integer, nullable=False, default=5)
    kron_budget = Column(Integer)            # kronor/week — MUST be present (Phase 5 gate)
    selected_stores = Column(String)         # comma-separated store ids, <= MAX_SELECTED_STORES
    # MC 1355.16 (T10b §2/§3): store-level selection per postnummer.
    #   postal_code     — digits-only Swedish postnummer, e.g. "41451"
    #   resolved_stores — JSON {"resolved_at": iso, "chains": {chain: {
    #                       "status": "ok"|"error", "error": str?,
    #                       "stores": [ResolvedStore...]}}}
    # Both nullable: absent = the user has not saved a postnummer. The
    # per-chain status and resolved_at are PERSISTED so staleness and partial
    # failure stay visible in every later GET (T10b §10-F7).
    postal_code = Column(String, nullable=True)
    resolved_stores = Column(Text, nullable=True)
    # MC 1355.18 (T11): antal barn (informational — does NOT feed servings
    # planning in this card) and the kid-friendly preference (0/1). Both
    # nullable: absent = the user has not saved a value (postal_code rule).
    num_children = Column(Integer, nullable=True)
    prefer_kid_friendly = Column(Integer, nullable=True)  # 0/1
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User")              # Phase 5 reads profile via authenticated User

    def __repr__(self):
        return f"<Profile user_id={self.user_id} kron_budget={self.kron_budget}>"
