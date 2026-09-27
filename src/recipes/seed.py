"""MODULE M6 — recipe-db starter seed (idempotent).

REV6 C-RDB ``seed_starter(conn) -> int`` (src/recipes/seed.py). Provides the
concrete in-project recipe set so the planner is never starved. Idempotent and
rerun-safe: each recipe upserts on UNIQUE title, so re-running adds nothing and
never duplicates. Returns the number of rows newly written (0 on a full rerun).
"""
from sqlalchemy.orm import Session

from recipes.store import upsert_recipe, Recipe

# Hand-curated starter roster of Swedish kvaellsmatsrecept (~18). Each carries the
# fields in REV6's Recipe schema. ingredients_json/allergens_json are read as Python
# values for maintainability and serialised here. created_at stamped once at import.
STARTER_ROSTER = [
    {
        "title": "Köttbullar med gräddsås och potatis",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "köttfärs", "qty": 500, "unit": "g"},
                        {"name": "potatis", "qty": 800, "unit": "g"},
                        {"name": "grädde", "qty": 2, "unit": "dl"}],
        "allergens": ["mjölk"],
    },
    {
        "title": "Pannkakor med sylt",
        "category": "husmanskost", "servings": 4, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "mjöl", "qty": 3, "unit": "dl"},
                        {"name": "mjölk", "qty": 6, "unit": "dl"},
                        {"name": "ägg", "qty": 3, "unit": "st"}],
        "allergens": ["mjölk", "gluten", "ägg"],
    },
    {
        "title": "Korv stroganoff",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "falukorv", "qty": 400, "unit": "g"},
                        {"name": "tomatpuré", "qty": 1, "unit": "dl"},
                        {"name": "grädde", "qty": 2, "unit": "dl"},
                        {"name": "ris", "qty": 4, "unit": "dl"}],
        "allergens": ["mjölk"],
    },
    {
        "title": "Tacopaj",
        "category": "husmanskost", "servings": 6, "vegetarian": 0,
        "budget_tier": "mid",
        "kid_friendly": 1,
        "ingredients": [{"name": "köttfärs", "qty": 500, "unit": "g"},
                        {"name": "tacosås", "qty": 1, "unit": "dl"},
                        {"name": "pajdeg", "qty": 1, "unit": "paket"},
                        {"name": "ost", "qty": 200, "unit": "g"}],
        "allergens": ["mjölk", "gluten"],
    },
    {
        "title": "Fiskgratäng med potatis",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "mid",
        "kid_friendly": 0,
        "ingredients": [{"name": "vitfiskfilé", "qty": 500, "unit": "g"},
                        {"name": "potatis", "qty": 700, "unit": "g"},
                        {"name": "ost", "qty": 150, "unit": "g"},
                        {"name": "grädde", "qty": 3, "unit": "dl"}],
        "allergens": ["mjölk", "fisk"],
    },
    {
        "title": "Köttfärssås och spagetti",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "köttfärs", "qty": 400, "unit": "g"},
                        {"name": "krossade tomater", "qty": 500, "unit": "g"},
                        {"name": "lök", "qty": 1, "unit": "st"},
                        {"name": "spagetti", "qty": 400, "unit": "g"}],
        "allergens": ["gluten"],
    },
    {
        "title": "Ugnsbakad lax med kokt potatis",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "premium",
        "kid_friendly": 0,
        "ingredients": [{"name": "laxfilé", "qty": 600, "unit": "g"},
                        {"name": "potatis", "qty": 800, "unit": "g"},
                        {"name": "citron", "qty": 1, "unit": "st"}],
        "allergens": ["fisk"],
    },
    {
        "title": "Vegetarisk lasagne",
        "category": "vegetarisk", "servings": 6, "vegetarian": 1,
        "budget_tier": "mid",
        "kid_friendly": 0,
        "ingredients": [{"name": "lasagneplattor", "qty": 1, "unit": "paket"},
                        {"name": "spenat", "qty": 300, "unit": "g"},
                        {"name": "ricotta", "qty": 250, "unit": "g"},
                        {"name": "tomatsås", "qty": 500, "unit": "g"}],
        "allergens": ["mjölk", "gluten"],
    },
    {
        "title": "Linssallad med fetaost",
        "category": "vegetarisk", "servings": 4, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 0,
        "ingredients": [{"name": "röda linser", "qty": 300, "unit": "g"},
                        {"name": "fetaost", "qty": 150, "unit": "g"},
                        {"name": "tomater", "qty": 3, "unit": "st"}],
        "allergens": ["mjölk"],
    },
    {
        "title": "Kikärtsgryta med kokosmjölk",
        "category": "vegetarisk", "servings": 4, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 0,
        "ingredients": [{"name": "kikärtor", "qty": 400, "unit": "g"},
                        {"name": "kokosmjölk", "qty": 400, "unit": "ml"},
                        {"name": "curry", "qty": 1, "unit": "msk"},
                        {"name": "ris", "qty": 4, "unit": "dl"}],
        "allergens": [],
    },
    {
        "title": "Quesadillas med bönor",
        "category": "vegetarisk", "servings": 4, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "tortillabröd", "qty": 8, "unit": "st"},
                        {"name": "svarta bönor", "qty": 400, "unit": "g"},
                        {"name": "ost", "qty": 200, "unit": "g"}],
        "allergens": ["mjölk", "gluten"],
    },
    {
        "title": "Rostade grönsaker med hummus",
        "category": "vegetarisk", "servings": 4, "vegetarian": 1,
        "budget_tier": "mid",
        "kid_friendly": 0,
        "ingredients": [{"name": "broccoli", "qty": 1, "unit": "st"},
                        {"name": "morötter", "qty": 4, "unit": "st"},
                        {"name": "hummus", "qty": 200, "unit": "g"}],
        "allergens": ["sesam"],
    },
    {
        "title": "Pasta med tomaatsås och basilika",
        "category": "vegetarisk", "servings": 2, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 1,
        "ingredients": [{"name": "pasta", "qty": 250, "unit": "g"},
                        {"name": "tomatsås", "qty": 400, "unit": "g"},
                        {"name": "basilika", "qty": 1, "unit": "kruka"}],
        "allergens": ["gluten"],
    },
    {
        "title": "Kyckling med ris och currysås",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "mid",
        "kid_friendly": 0,
        "ingredients": [{"name": "kycklingfilé", "qty": 500, "unit": "g"},
                        {"name": "ris", "qty": 4, "unit": "dl"},
                        {"name": "currysås", "qty": 3, "unit": "dl"}],
        "allergens": [],
    },
    {
        "title": "Grönsakssoppa med bröd",
        "category": "husmanskost", "servings": 4, "vegetarian": 1,
        "budget_tier": "budget",
        "kid_friendly": 0,
        "ingredients": [{"name": "rotfrukter", "qty": 600, "unit": "g"},
                        {"name": "grönsaksbuljong", "qty": 1, "unit": "l"},
                        {"name": "bröd", "qty": 1, "unit": "limpa"}],
        "allergens": ["gluten"],
    },
    {
        "title": "Pytt i panna med ägg",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "budget",
        "kid_friendly": 0,
        "ingredients": [{"name": "pyttipanna", "qty": 800, "unit": "g"},
                        {"name": "ägg", "qty": 4, "unit": "st"}],
        "allergens": ["ägg"],
    },
    {
        "title": "Unsbakad falukorv med potatismos",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "budget",
        "kid_friendly": 0,
        "ingredients": [{"name": "falukorv", "qty": 600, "unit": "g"},
                        {"name": "potatis", "qty": 800, "unit": "g"},
                        {"name": "mjölk", "qty": 2, "unit": "dl"}],
        "allergens": ["mjölk"],
    },
    {
        "title": "Pasta carbonara",
        "category": "husmanskost", "servings": 4, "vegetarian": 0,
        "budget_tier": "premium",
        "kid_friendly": 0,
        "ingredients": [{"name": "spagetti", "qty": 400, "unit": "g"},
                        {"name": "bacon", "qty": 200, "unit": "g"},
                        {"name": "ägg", "qty": 4, "unit": "st"},
                        {"name": "parmesan", "qty": 100, "unit": "g"}],
        "allergens": ["ägg", "mjölk", "gluten"],
    },
]


def seed_starter(conn: Session) -> int:
    """CONTRACT C-RDB: idempotent starter roster; rerun-safe. Returns rows newly
    written (0 on a full rerun — nothing duplicates because title is UNIQUE)."""
    import json
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = conn.query(Recipe).count()
    for spec in STARTER_ROSTER:
        row = dict(spec)
        row["ingredients_json"] = json.dumps(spec["ingredients"], ensure_ascii=False)
        row["allergens_json"] = json.dumps(spec.get("allergens", []), ensure_ascii=False)
        row["created_at"] = created_at
        row["source_url"] = ""
        row.pop("ingredients", None)   # raw list never reaches the ORM
        row.pop("allergens", None)     # only the serialised _json columns persist
        upsert_recipe(conn, row)
    after = conn.query(Recipe).count()
    return after - before  # rows NEWLY inserted (0 on a full rerun)
