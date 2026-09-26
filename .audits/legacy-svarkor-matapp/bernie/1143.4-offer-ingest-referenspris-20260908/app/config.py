"""Shared configuration for the matapp offer-ingest line (Phase 4 T3).

Defines GrocerConfig (per-chain feed endpoint) and the chain-mapping table CHAIN_MAP
that the normalizer plays on. REUSES the POC Kwallsmat config shape (REV6 §cross-module:
"reuses the chain-mapping table in config") — id_prefix/round_cents carried exactly, so
Phase 6 optimizer reads the same normalized identities.

CHAIN_MAP rule shape (ASSUMED from the design §9, minimal concrete choice — same as POC):
  - id_prefix: prepended to external_id to form the normalized identity ('' = identity)
  - round_cents: if set, round resulting price_cents to nearest multiple (None = exact)
Any unknown chain falls back to CHAIN_DEFAULT (identity, exact).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GrocerConfig:
    grocer_id: str
    endpoint: str
    token: str = ""
    headers: dict = field(default_factory=dict)
    chain: str = ""  # chain key; defaults to grocer_id in PlannerConfig.grocer(...)

    @classmethod
    def grocer(cls, grocer_id, endpoint, token="", headers=None, chain=None):
        chain = chain or grocer_id
        return cls(
            grocer_id=grocer_id,
            endpoint=endpoint,
            token=token,
            headers=headers or {},
            chain=chain,
        )


CHAIN_MAP = {
    "ica":    {"id_prefix": "ica-", "round_cents": None},
    "willys": {"id_prefix": "", "round_cents": 10},
    "coop":   {"id_prefix": "coop-", "round_cents": None},
}

CHAIN_DEFAULT = {"id_prefix": "", "round_cents": None}
