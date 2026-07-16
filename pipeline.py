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


def process_log(log_text, on_progress=None):
    """
    Takes a free-text food log and returns a dict:
        {
            "items": [ ... per-item detail, including unmatched ... ],
            "totals": { nutrient_name: {"amount": ..., "unit": ...} }
        }

    on_progress: optional callable(str) invoked with a short human-readable
    status message as the pipeline moves through real stages. Used to power
    a live progress indicator in the UI; safe to omit for non-UI callers.
    """
    def report(msg):
        if on_progress:
            on_progress(msg)

    report("Parsing your log...")
    parsed_items = parse_log(log_text)

    matched_items = []
    item_details = []
    total_items = len(parsed_items)

    for i, parsed in enumerate(parsed_items, start=1):
        food_name = parsed["food_name"]

        if total_items > 1:
            report(f"Matching item {i} of {total_items}: {food_name}...")
        else:
            report(f"Matching '{food_name}' to USDA data...")

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

        report(f"Fetching nutrient data for {food_name}...")
        matched_candidate = next((c for c in candidates if c["fdc_id"] == fdc_id), None)
        nutrients = get_nutrients(fdc_id)

        if not nutrients:
            # The chosen fdc_id passed validation as a real search result,
            # but USDA's detail endpoint has no data for it (their search
            # index can lag behind their detail database, so an id can
            # show up as a valid candidate but 404 on lookup). Don't
            # silently report this as a successful "matched" item with
            # zero nutrients, that's misleading. Instead, retry against
            # the remaining candidates, excluding the dead one, so a
            # working match can still be found.
            remaining = [c for c in candidates if c["fdc_id"] != fdc_id]
            retry_fdc_id = match_food_llm(food_name, remaining) if remaining else None

            if retry_fdc_id is not None:
                retry_nutrients = get_nutrients(retry_fdc_id)
                if retry_nutrients:
                    fdc_id = retry_fdc_id
                    nutrients = retry_nutrients
                    matched_candidate = next(
                        (c for c in remaining if c["fdc_id"] == fdc_id), None
                    )

        if not nutrients:
            # Still nothing usable after retrying, report clearly instead
            # of showing a fake zero-nutrient match.
            item_details.append({
                "food_name": food_name,
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
                "status": "no_nutrient_data",
                "matched_description": matched_candidate["description"] if matched_candidate else None,
            })
            continue

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

    report("Crunching nutrient totals...")
    totals = compute_daily_totals(matched_items)

    return {
        "items": item_details,
        "totals": totals,
    }