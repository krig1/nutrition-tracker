"""
Client for the USDA FoodData Central API, with a local SQLite cache
so we don't re-fetch nutrient data for foods we've already looked up.

Requires: export FDC_API_KEY="your-key-here"
"""
import os
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("FDC_API_KEY")
BASE_URL = "https://api.nal.usda.gov/fdc/v1"
DB_PATH = "foods.db"

# Data types to prefer: Foundation and SR Legacy are both clean,
# reliable sources for common whole foods (vs. Branded, which is huge
# and inconsistent). We query them as SEPARATE calls (so one dataset's
# relevance scoring doesn't drown out the other, e.g. "milk" matching a
# Foundation cracker before an SR Legacy whole milk entry) but MERGE
# their results into one combined candidate pool. This matters because
# Foundation and SR Legacy don't have full overlap: Foundation is a
# narrower dataset and may not contain a food's "default" everyday form
# at all (e.g. it has sweetened condensed/evaporated/dry milk but not
# plain whole milk, which only lives in SR Legacy). Stopping as soon as
# Foundation returns anything would silently hide the SR Legacy match
# the matcher actually needs to see. Branded is only queried as a last
# resort, if the combined Foundation + SR Legacy pool is empty.
RELIABLE_DATA_TYPES = ["Foundation", "SR Legacy"]


def _get_connection():
    return sqlite3.connect(DB_PATH)


def search_food(query, page_size=15):
    """
    Search FDC for foods matching a query string.
    Queries Foundation and SR Legacy separately, then merges both result
    sets into one candidate pool (so the matcher sees the full range of
    plain/default food forms, not whichever dataset happened to answer
    first). Falls back to Branded only if that combined pool is empty,
    so packaged/branded-only items (sodas, packaged snacks) still work.
    Returns a list of dicts: [{fdc_id, description, data_type}, ...]
    """
    if not API_KEY:
        raise RuntimeError("FDC_API_KEY environment variable not set")

    combined = []
    seen_ids = set()
    for data_type in RELIABLE_DATA_TYPES:
        for item in _search_by_data_types(query, [data_type], page_size):
            if item["fdc_id"] not in seen_ids:
                combined.append(item)
                seen_ids.add(item["fdc_id"])

    if combined:
        return combined

    return _search_by_data_types(query, ["Branded"], page_size)


def _search_by_data_types(query, data_types, page_size):
    params = {
        "api_key": API_KEY,
        "query": query,
        "pageSize": page_size,
        "dataType": data_types,
    }
    response = requests.get(f"{BASE_URL}/foods/search", params=params)
    response.raise_for_status()
    data = response.json()

    results = []
    for food in data.get("foods", []):
        results.append({
            "fdc_id": food["fdcId"],
            "description": food["description"],
            "data_type": food.get("dataType"),
        })
    return results


def get_nutrients(fdc_id):
    """
    Get the full nutrient profile for a specific food, per 100g.
    Checks local cache first; falls back to the FDC API and caches
    the result if not found locally.
    Returns a list of dicts: [{nutrient_name, unit, amount_per_100g}, ...]
    """
    cached = _get_cached_nutrients(fdc_id)
    print(f"[DEBUG] cache lookup for fdc_id={fdc_id}: "
          f"{'HIT, ' + str(len(cached)) + ' nutrients' if cached else 'MISS'}")
    if cached:
        print(f"[DEBUG] cached sample: {cached[:3]}")
    if cached:
        return cached

    if not API_KEY:
        raise RuntimeError("FDC_API_KEY environment variable not set")

    params = {"api_key": API_KEY}
    response = requests.get(f"{BASE_URL}/food/{fdc_id}", params=params)

    if response.status_code == 404:
        # Invalid, deprecated, or no-longer-available fdc_id. USDA's
        # search index can occasionally lag behind their detail database,
        # so an id can appear as a valid search result but 404 here.
        # Treat as no data rather than crashing the pipeline; pipeline.py
        # handles retrying with a different candidate when this happens.
        return []

    response.raise_for_status()
    data = response.json()

    nutrients = []
    seen = set()
    for entry in data.get("foodNutrients", []):
        nutrient_info = entry.get("nutrient", {})
        name = nutrient_info.get("name")
        unit = nutrient_info.get("unitName")
        amount = entry.get("amount")
        if not name or amount is None:
            continue

        # FDC sometimes lists the same nutrient twice under different
        # calculation methods (e.g. Energy via "Atwater General Factors"
        # vs "Atwater Specific Factors"), both under the same name and
        # unit. Keep only the first occurrence to avoid double-counting.
        key = (name, unit)
        if key in seen:
            continue
        seen.add(key)

        nutrients.append({
            "nutrient_name": name,
            "unit": unit,
            "amount_per_100g": amount,
        })

    _cache_food(fdc_id, data.get("description", ""), data.get("dataType", ""), nutrients)
    return nutrients


def _get_cached_nutrients(fdc_id):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM foods WHERE fdc_id = ?", (fdc_id,))
    if cur.fetchone() is None:
        conn.close()
        return None

    cur.execute(
        "SELECT nutrient_name, unit, amount_per_100g FROM nutrients WHERE fdc_id = ?",
        (fdc_id,)
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return None

    return [
        {"nutrient_name": r[0], "unit": r[1], "amount_per_100g": r[2]}
        for r in rows
    ]


def _cache_food(fdc_id, description, data_type, nutrients):
    conn = _get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO foods (fdc_id, description, data_type) VALUES (?, ?, ?)",
        (fdc_id, description, data_type)
    )

    cur.execute("DELETE FROM nutrients WHERE fdc_id = ?", (fdc_id,))
    cur.executemany(
        "INSERT INTO nutrients (fdc_id, nutrient_name, unit, amount_per_100g) VALUES (?, ?, ?, ?)",
        [(fdc_id, n["nutrient_name"], n["unit"], n["amount_per_100g"]) for n in nutrients]
    )

    conn.commit()
    conn.close()