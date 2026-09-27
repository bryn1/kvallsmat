"""Phase 6 (T5) optimizer-ratio-3 — recorded recipe set for the harness.

A small hand-curated subset of the Phase-2/POC starter roster, kept intentionally
compact (coding-discipline) but rich enough that the greedy produces three
mutually-distinct weekly plans. Shape matches the C-RDB Recipe model from Phase 2
(src/recipes/store.py): title, category, servings, vegetarian, budget_tier,
ingredients_json, allergens_json.

``ingredients_json`` holds a JSON list of ``{"name": ..., "qty": ..., "unit": ...}``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Recipe:
    title: str
    category: str
    servings: int
    vegetarian: int
    budget_tier: str
    kid_friendly: int = 0  # MC 1355.18 (T11): 0/1 barnvänligt (roster mirror)
    ingredients: list = field(default_factory=list)
    allergens: list = field(default_factory=list)

    @property
    def ingredients_json(self) -> str:
        return json.dumps(self.ingredients, ensure_ascii=False)

    @property
    def allergens_json(self) -> str:
        return json.dumps(self.allergens, ensure_ascii=False)


ROSTER = [
    Recipe(
        title="Köttbullar med gräddsås och potatis", category="husmanskost",
        servings=4, vegetarian=0, budget_tier="budget",
        kid_friendly=1,
        ingredients=[{"name": "köttfärs", "qty": 500, "unit": "g"},
                     {"name": "potatis", "qty": 800, "unit": "g"},
                     {"name": "grädde", "qty": 2, "unit": "dl"}],
        allergens=["mjölk"],
    ),
    Recipe(
        title="Köttfärssås och spagetti", category="husmanskost",
        servings=4, vegetarian=0, budget_tier="budget",
        kid_friendly=1,
        ingredients=[{"name": "köttfärs", "qty": 400, "unit": "g"},
                     {"name": "krossade tomater", "qty": 500, "unit": "g"},
                     {"name": "lök", "qty": 1, "unit": "st"},
                     {"name": "spagetti", "qty": 400, "unit": "g"}],
        allergens=["gluten"],
    ),
    Recipe(
        title="Ugnsbakad lax med kokt potatis", category="husmanskost",
        servings=4, vegetarian=0, budget_tier="premium",
        kid_friendly=0,
        ingredients=[{"name": "laxfilé", "qty": 600, "unit": "g"},
                     {"name": "potatis", "qty": 800, "unit": "g"},
                     {"name": "citron", "qty": 1, "unit": "st"}],
        allergens=["fisk"],
    ),
    Recipe(
        title="Kyckling med ris och currysås", category="husmanskost",
        servings=4, vegetarian=0, budget_tier="mid",
        kid_friendly=0,
        ingredients=[{"name": "kycklingfilé", "qty": 500, "unit": "g"},
                     {"name": "ris", "qty": 4, "unit": "dl"},
                     {"name": "currysås", "qty": 3, "unit": "dl"}],
        allergens=[],
    ),
    Recipe(
        title="Korv stroganoff", category="husmanskost",
        servings=4, vegetarian=0, budget_tier="budget",
        kid_friendly=1,
        ingredients=[{"name": "falukorv", "qty": 400, "unit": "g"},
                     {"name": "tomatpuré", "qty": 1, "unit": "dl"},
                     {"name": "grädde", "qty": 2, "unit": "dl"},
                     {"name": "ris", "qty": 4, "unit": "dl"}],
        allergens=["mjölk"],
    ),
    # A deliberately LOW-ratio dish (none of its ingredients on extrapris): it exists
    # so the RED case (threshold 0.0 / majority ignored) can select it and trip the
    # >= 0.5 invariant check. With the correct threshold it is filtered out (ratio 0.0).
    Recipe(
        title="Pannkakor med sylt", category="husmanskost",
        servings=4, vegetarian=1, budget_tier="budget",
        kid_friendly=1,
        ingredients=[{"name": "mjöl", "qty": 3, "unit": "dl"},
                     {"name": "mjölk", "qty": 6, "unit": "dl"},
                     {"name": "ägg", "qty": 3, "unit": "st"}],
        allergens=["mjölk", "gluten", "ägg"],
    ),
]


def recipes() -> list[Recipe]:
    return list(ROSTER)
