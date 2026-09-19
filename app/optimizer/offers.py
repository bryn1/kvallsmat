"""Phase 6 (T5) optimizer-ratio-3 — recorded OFFER set for the harness.

Recorded in-week offers for one grocer/week (willys, week 2026-W37), each carrying the
reference price persisted by Phase 4 (closure-gap 1) plus the Phase-4 ``is_extraprice``
per-ingredient flag. Shape matches the Phase-2 ``Offer`` model (offers_db.py) with the
Phase-4 reference columns ``regular_price_cents`` / ``savings_cents`` and the
normalizer-set ``is_extraprice``.

An offer is *extrapris* iff ``regular_price_cents > price_cents`` (measurable
discount) — the exact Phase-4 ``is_extraprice`` semantics the optimizer's ratio rule
consumes. ``price_cents`` is the sale price; ``savings_cents = regular - price``.

The set is arranged so that every starter dish in recipes.py reaches ``andel_extrapris
>= 0.5`` (its majority of ingredients hit by an extrapris offer), while different
dishes see different hit counts — so the greedy, under different seeds, yields three
mutually distinct weekly plans that ALL satisfy the threshold.
"""
from __future__ import annotations

from dataclasses import dataclass

WEEK_KEY = "2026-W37"


@dataclass
class Offer:
    offer_id: int
    grocer_id: str
    external_id: str
    week_key: str
    name: str
    price_cents: int
    regular_price_cents: int | None
    savings_cents: int | None
    unit: str = ""
    is_extraprice: bool = False

    def __post_init__(self):
        if self.regular_price_cents is not None:
            self.is_extraprice = self.regular_price_cents > self.price_cents


def _o(oid, name, price, regular, unit=""):
    """Build one extrapris offer (regular strictly above sale) with derived savings."""
    savings = (regular - price) if regular is not None else None
    return Offer(
        offer_id=oid, grocer_id="willys", external_id=f"w37-{oid:04d}",
        week_key=WEEK_KEY, name=name, price_cents=price,
        regular_price_cents=regular, savings_cents=savings, unit=unit,
    )


# Every offer below is on extrapris (regular_price_cents > price_cents), deliberately
# spread to hit the majority of each dish's ingredients.
OFFERS = [
    _o(1, "Köttfärs nöt 500g", 4990, 7129, "g"),
    _o(2, "Potatis fast 2kg", 1990, 2990, "kg"),
    _o(3, "Grädde 5dl", 1690, 2190, "dl"),
    _o(4, "Krossade tomater 500g", 990, 1590, "g"),
    _o(5, "Lök gul 1kg", 1490, 1990, "kg"),
    _o(6, "Spagetti 400g", 1090, 1590, "g"),
    _o(7, "Laxfilé färsk 600g", 9900, 13990, "g"),
    _o(8, "Citron ekologisk 1st", 590, 890, "st"),
    _o(9, "Kycklingfilé 500g", 6990, 8990, "g"),
    _o(10, "Ris jasmin 1kg", 2490, 3290, "kg"),
    _o(11, "Falukorv 400g", 2590, 3190, "g"),
    _o(12, "Tomatpuré 1dl", 790, 1090, "dl"),
]


def offers() -> list[Offer]:
    return list(OFFERS)
