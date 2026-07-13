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

# Data types to prefer: Foundation and SR Legacy are the cleanest,
# most reliable sources for common whole foods (vs. Branded, which
# is huge and inconsistent). We search across these two first.
PREFERRED_DATA_TYPES = ["Foundation", "SR Legacy"]


def _get_connection():
    return sqlite3.connect(DB_PATH)


def search_food(query, page_size=5):
    """
    Search FDC for foods matching a query string.
    Tries Foundation/SR Legacy first (cleaner data for whole foods).
    Falls back to Branded (packaged/branded products) if nothing is found,
    so common items like sodas or packaged snacks still return results.
    Returns a list of dicts: [{fdc_id, description, data_type}, ...]
    """
    if not API_KEY:
        raise RuntimeError("FDC_API_KEY environment variable not set")

    results = _search_by_data_types(query, PREFERRED_DATA_TYPES, page_size)
    if results:
        return results

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
    if cached:
        return cached

    if not API_KEY:
        raise RuntimeError("FDC_API_KEY environment variable not set")

    params = {"api_key": API_KEY}
    response = requests.get(f"{BASE_URL}/food/{fdc_id}", params=params)

    if response.status_code == 404:
        # Invalid or no-longer-available fdc_id; treat as no data rather
        # than crashing the whole pipeline.
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