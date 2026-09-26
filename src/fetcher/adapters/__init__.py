"""M2 fetcher.adapters — per-grocer real offer fetchers (MC 1355.4).

Dispatch layer over the RawFeed contract (fetcher.grocer owns the contract):
``fetch(grocer_cfg, week_key, session)`` returns a RawFeed dict for a grocer
with a real adapter, or ``None`` when no adapter matches (the caller then falls
back to the legacy ``{base}/veckans-extrapris`` pull). All adapters are
fail-tolerant: a network error, non-200 response, bad HTML or unparsable blob
yields ``entries: []`` — never a raise.
"""
from __future__ import annotations

from . import ica as _ica
from . import lidl as _lidl
from . import tjek as _tjek
from ._common import get_text, week_start  # re-exported for callers/tests

# chain/grocer_id -> module with a pull(cfg, week_key, session) -> RawFeed
_ADAPTERS = {
    "ica": _ica,
    "lidl": _lidl,
    # Willys + Coop publish their veckoblad through Tjek (MC 1355.10).
    "willys": _tjek,
    "coop": _tjek,
}


def fetch(grocer_cfg, week_key: str, session=None) -> dict | None:
    """Run the real adapter for this grocer, or None if there is none."""
    adapter = _ADAPTERS.get(grocer_cfg.chain or grocer_cfg.grocer_id)
    if adapter is None:
        return None
    return adapter.pull(grocer_cfg, week_key, session)
