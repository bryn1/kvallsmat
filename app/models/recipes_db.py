"""app.models.recipes_db — RE-EXPORT shim (MC 10037, PORT-PLAN P1-a0).

The ``recipes`` table's SINGLE canonical definition lives in the motor home
``src/recipes/store.py`` (CONTRACT C-RDB). This module mirrors the ``offers_db``
shim precedent (MC 1355.5): importing the motor's ``Recipe`` here keeps
``app.models`` registering the table for boot() while every app-side consumer
imports ONLY via this shim — a second mapping of the same tablename on the
shared ``database.Base`` raises ``InvalidRequestError`` the moment both import
paths load, and the sibling top-level import idiom (``from recipes.store
import ...``, run_motor.py) is exactly that hazard when src/ joins sys.path.
The aliasing seam in app.db handles that seam once; see the comment in
tests/test_recipe_kid_friendly.py for the repo-sanctioned pattern.
"""
from __future__ import annotations

from src.recipes.store import (  # noqa: F401  (re-export + table registration)
    Recipe,
    c_rdb_list_all,
)
