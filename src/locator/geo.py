"""src.locator.geo — the ONE distance function for the locator package (T10b §2).

Shared by the willys and coop locators (and any future one) so there are never
two haversine copies. stdlib math only.
"""
from __future__ import annotations

import math

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two (lat, lon) points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * math.asin(math.sqrt(a)) * _EARTH_RADIUS_KM
