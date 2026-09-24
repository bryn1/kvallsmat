"""app.models.offers_db — RE-EXPORT shim (MC 1355.5).

The ``offers`` table's SINGLE canonical definition lives in the motor home
``src/offers_db/store.py`` (CONTRACT C5 / C-OW). This module used to carry a
second mapping of the same tablename on the shared ``database.Base``, which
raises ``InvalidRequestError`` the moment the menu router (MC 1355.5) imports
the motor store alongside the web models. The duplicate is retired: import the
motor's Offer here so ``app.models`` still registers the table for boot().

The reference-price columns (closure-gap 1: ``regular_price_cents`` /
``savings_cents``) moved into the canonical definition — schema unchanged.
"""
from __future__ import annotations

from src.offers_db.store import Offer  # noqa: F401  (re-export + table registration)
