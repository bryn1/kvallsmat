"""src.locator.models — shared shapes for the locator package (T10b §2).

One shape for every chain's resolved stores (``ResolvedStore``) and one for the
per-chain resolve outcome (``ChainStatus``), both JSON-roundtrippable because
the resolved list is PERSISTED as JSON on the profile row (T10b §2).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResolvedStore:
    """One physical store a postnummer resolved to, for one chain."""

    chain: str
    store_id: str
    store_name: str
    lat: float
    lon: float
    distance_km: float

    def to_dict(self) -> dict:
        return {
            "chain": self.chain,
            "store_id": self.store_id,
            "store_name": self.store_name,
            "lat": self.lat,
            "lon": self.lon,
            "distance_km": self.distance_km,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResolvedStore | None":
        """Rebuild from the persisted JSON shape; None on a malformed entry."""
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                chain=str(data["chain"]),
                store_id=str(data["store_id"]),
                store_name=str(data["store_name"]),
                lat=float(data["lat"]),
                lon=float(data["lon"]),
                distance_km=float(data["distance_km"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class ChainStatus:
    """Per-chain resolve outcome, persisted beside the stores (T10b §10-F7)."""

    chain: str
    status: str  # "ok" | "error"
    error: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"chain": self.chain, "status": self.status}
        if self.error is not None:
            out["error"] = self.error
        return out
