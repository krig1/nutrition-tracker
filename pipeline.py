"""
Chains the full pipeline together:
  free-text log -> parsed food items -> FDC matches -> nutrient totals

This is the main entry point the web app (and future scoring/recommendation
steps) will call.
"""
from parser import parse_log
from fdc_client import search_food, get_nutrients, _search_by_data_types
from matcher import match_food_llm
from aggregator import compute_daily_totals


def process_log(log_text):
    """
    Takes a free-text food log and returns a dict:
        {
            "items": [ ... per-item detail, including unmatched ... ],
            "totals": { nutrient_name: {"amount": ..., "unit": ...} }
        }
    """
    parsed_items = parse_log(log_text)

    matched_items = []
    item_details = []

    for parsed in parsed_items:
        food_name = parsed["food_name"]
        candidates = search_food(food_name)

        if not candidates:
            item_details.append({
                "food_name": food_name,
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
                "status": "no_candidates",
                "matched_description": None,
            })
            continue

        fdc_id = match_food_llm(food_name, candidates)

        if fdc_id is None:
            # First-tier candidates existed but none were a good match
            # (e.g. searching "coca-cola" surfaces other Coca-Cola-brand
            # products in SR Legacy, but not the actual soda). Retry
            # explicitly against Branded before giving up.
            branded_candidates = _search_by_data_types(food_name, ["Branded"], page_size=5)
            if branded_candidates:
                fdc_id = match_food_llm(food_name, branded_candidates)
                if fdc_id is not None:
                    candidates = branded_candidates

        if fdc_id is None:
            item_details.append({
                "food_name": food_name,
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
                "status": "no_confident_match",
                "matched_description": None,
            })
            continue

        matched_candidate = next((c for c in candidates if c["fdc_id"] == fdc_id), None)
        nutrients = get_nutrients(fdc_id)

        matched_items.append({
            "quantity": parsed["quantity"],
            "unit": parsed["unit"],
            "nutrients": nutrients,
        })

        item_details.append({
            "food_name": food_name,
            "quantity": parsed["quantity"],
            "unit": parsed["unit"],
            "status": "matched",
            "matched_description": matched_candidate["description"] if matched_candidate else None,
            "fdc_id": fdc_id,
        })

    totals = compute_daily_totals(matched_items)

    return {
        "items": item_details,
        "totals": totals,
    }