"""Shared configuration for the Kwallsmat ingest line (M1 scheduler / M2 fetcher / M3 normalizer).

Defines GrocerConfig + PlannerConfig used by CONTRACT C1/C2, and the chain-mapping table
CHAIN_MAP that CONTRACT C4 normalizer plays on (per REV6 §cross-module note:
"reuses the chain-mapping table in config").

CHAIN_MAP rule shape (carried as ASSUMED from the design, §9 — see MODULE M3 in
212.1-rev6 for the contract; the exact rule set is our concrete minimal choice):
  - id_prefix: prepended to external_id to form the normalized identity ('' = identity)
  - round_cents: if set, round resulting price_cents to the nearest multiple (None = exact)
Any unknown chain falls back to {"id_prefix": "", "round_cents": None} (identity, exact).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace


@dataclass(frozen=True)
class GrocerConfig:
    grocer_id: str
    endpoint: str
    token: str = ""
    headers: dict = field(default_factory=dict)
    chain: str = ""   # chain key; defaults to grocer_id in PlannerConfig.grocer(...)


@dataclass(frozen=True)
class PlannerConfig:
    grocers: list = field(default_factory=list)   # list[GrocerConfig]
    week_override: str = ""                       # optional pinned week_key ('' = compute)

    @classmethod
    def grocer(cls, grocer_id, endpoint, token="", headers=None, chain=None):
        chain = chain or grocer_id
        return GrocerConfig(grocer_id=grocer_id, endpoint=endpoint, token=token,
                            headers=headers or {}, chain=chain)


CHAIN_MAP = {
    "ica":    {"id_prefix": "ica-", "round_cents": None},
    "willys": {"id_prefix": "", "round_cents": 10},
    "coop":   {"id_prefix": "coop-", "round_cents": None},
}

CHAIN_DEFAULT = {"id_prefix": "", "round_cents": None}
