"""app.profile_service — per-user menu-profile persistence (Phase 5 T4 profile, gate C4).

The profile is stored AGAINST an authenticated session: the caller must have resolved
an opaque session token to a ``users.User`` (Phase 3 auth) and pass that user here.
There is exactly ONE profile row per user (the ``profile.user_id`` column is UNIQUE),
upserted on save and read back on load — so a PUT-then-GET roundtrip returns the
stored fields identically (the gate-C4 "roundtrip-test").

Persisted per-user fields (PHASE0.md §P Phase 5 / profile model):
  * persons        — number of people to cook for
  * meal_days      — how many days the plan must cover
  * kron_budget    — kronor/week budget (MUST be present — gate C4 "kron-budget")
  * selected_stores— up to MAX_SELECTED_STORES (3) chosen store ids

Single concern: profile CRUD against the ``profile`` table. Auth/session resolution
lives in app/auth_service; HTTP wire-up is in app/routers/profile.py.
"""
from __future__ import annotations

import json

import app.db as dbm
import app.models  # noqa: F401  (register tables before queries)
from app.models.profile import Profile, MAX_SELECTED_STORES
from app.models.users import User


class ProfileData:
    """Plain value object describing a user's menu profile (ID-less, UI-facing).

    MC 1355.16 (T10b §2): ``postal_code`` (digits-only, or None) and
    ``resolved_stores`` (the persisted resolve JSON, or None) ride on the same
    value object — the profile row is already the per-user store context.
    """

    __slots__ = ("persons", "meal_days", "kron_budget", "selected_stores",
                 "postal_code", "resolved_stores")

    def __init__(self, persons: int, meal_days: int, kron_budget: int,
                 selected_stores: list[str], postal_code: str | None = None,
                 resolved_stores: dict | None = None) -> None:
        self.persons = persons
        self.meal_days = meal_days
        self.kron_budget = kron_budget
        self.selected_stores = list(selected_stores)
        self.postal_code = postal_code
        self.resolved_stores = resolved_stores

    def as_dict(self) -> dict:
        return {
            "persons": self.persons,
            "meal_days": self.meal_days,
            "kron_budget": self.kron_budget,
            "selected_stores": self.selected_stores,
            "postal_code": self.postal_code,
            "resolved_stores": self.resolved_stores,
        }

    def _store_list(self) -> str:
        # persist as comma-separated (the profile column is a String of store ids)
        return ",".join(self.selected_stores)


def _ensure_db() -> None:
    if dbm._Session is None:
        dbm.boot()


def save_profile(user: User, data: ProfileData) -> Profile:
    """Upsert *data* as the profile row for *user* (returns the persisted row)."""
    if data.kron_budget is None or data.kron_budget < 0:
        raise ValueError("kron_budget is required and must be >= 0 (gate C4)")
    if len(data.selected_stores) > MAX_SELECTED_STORES:
        raise ValueError(
            f"selected_stores may hold at most {MAX_SELECTED_STORES} stores"
        )

    _ensure_db()
    session = dbm._Session()
    try:
        row = session.query(Profile).filter_by(user_id=user.user_id).first()
        if row is None:
            row = Profile(user_id=user.user_id)
            session.add(row)
        row.persons = data.persons
        row.meal_days = data.meal_days
        row.kron_budget = data.kron_budget
        row.selected_stores = data._store_list()
        # MC 1355.16: persist the postnummer + the resolved-stores JSON
        # (resolved_at + per-chain status) so staleness/partial failure stay
        # visible in every later GET (T10b §10-F7).
        row.postal_code = data.postal_code
        row.resolved_stores = (
            json.dumps(data.resolved_stores)
            if data.resolved_stores is not None else None)
        session.commit()
        session.refresh(row)
        return row
    finally:
        session.close()


def load_profile(user: User) -> ProfileData | None:
    """Return the persisted profile for *user*, or None when none is saved yet."""
    _ensure_db()
    session = dbm._Session()
    try:
        row = session.query(Profile).filter_by(user_id=user.user_id).first()
        if row is None:
            return None
        stores = row.selected_stores.split(",") if row.selected_stores else []
        return ProfileData(
            persons=row.persons,
            meal_days=row.meal_days,
            kron_budget=row.kron_budget,
            selected_stores=stores,
            postal_code=row.postal_code,
            resolved_stores=_parse_resolved(row.resolved_stores),
        )
    finally:
        session.close()


def _parse_resolved(raw: str | None) -> dict | None:
    """Parse the persisted resolved_stores JSON; None when unset/malformed."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
