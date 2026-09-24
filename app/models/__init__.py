"""app.models — web-layer model modules for the matapp framtidsvision.

Phase 2 (T1) db-foundation: every model here declares its table on the shared
``database.Base`` and is imported BEFORE ``init_db`` (POC fix-2 idiom). Importing
``app.models`` (or any submodule) registers the table so ``boot()`` creates it
atomically with the rest of the schema.

DoD-required names: ``users``, ``profile``, ``offers_db`` — each carries a ``Base``
that is the shared ``database.Base`` (``print(users.Base, profile.Base)``).
"""
from . import users      # noqa: F401  (registers users table on Base)
from . import profile    # noqa: F401  (registers profile table on Base)
from . import offers_db  # noqa: F401  (registers offers table on Base)
from . import store_selection  # noqa: F401  (registers store_selection table, MC 1355.3)
