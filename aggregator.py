"""
Converts logged food quantities into grams, then aggregates matched
foods' nutrient data into daily totals.

KNOWN LIMITATION: "serving" is treated as 100g by default, since FDC
doesn't consistently provide a reliable serving-size-in-grams figure
across all foods. This is a rough approximation, not a precise
conversion, see README for discussion.

KNOWN LIMITATION: volume units (ml, cup, tbsp, etc.) are converted
assuming 1ml = 1g. Accurate for water-like liquids (soda, coffee,
milk), but less accurate for dense liquids like honey or oil.
"""

# Weight units -> grams
WEIGHT_TO_GRAMS = {
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.3495,
    "lb": 453.592,
}

# Volume units -> milliliters (then treated as grams, see limitation above)
VOLUME_TO_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "tsp": 4.92892,
    "tbsp": 14.7868,
    "cup": 236.588,
    "fl_oz": 29.5735,
}

DEFAULT_SERVING_GRAMS = 100.0


def convert_to_grams(quantity, unit):
    """
    Converts a (quantity, unit) pair as produced by parser.py into grams.
    """
    unit = unit.lower().strip()

    if unit in WEIGHT_TO_GRAMS:
        return quantity * WEIGHT_TO_GRAMS[unit]

    if unit in VOLUME_TO_ML:
        return quantity * VOLUME_TO_ML[unit]  # 1ml assumed = 1g

    if unit == "serving":
        return quantity * DEFAULT_SERVING_GRAMS

    # Unknown unit: fall back to the serving assumption rather than crash,
    # but this should be rare if parser.py is constrained to known units.
    return quantity * DEFAULT_SERVING_GRAMS


def compute_daily_totals(matched_items):
    """
    matched_items: list of dicts, each with:
        - quantity: float
        - unit: str
        - nutrients: list of {nutrient_name, unit, amount_per_100g}
          (as returned by fdc_client.get_nutrients)

    Returns: dict of {nutrient_name: {"amount": float, "unit": str}}
    summed across all items, scaled to the actual quantity consumed.
    """
    totals = {}

    for item in matched_items:
        grams = convert_to_grams(item["quantity"], item["unit"])
        scale_factor = grams / 100.0  # nutrients are given per 100g

        for nutrient in item["nutrients"]:
            name = nutrient["nutrient_name"]
            amount = nutrient["amount_per_100g"] * scale_factor
            unit = nutrient["unit"]
            key = (name, unit)  # keyed by name+unit so e.g. Energy (kcal) and Energy (kJ) don't merge

            if key not in totals:
                totals[key] = {"amount": 0.0, "unit": unit, "nutrient_name": name}
            totals[key]["amount"] += amount

    # Re-key the output by name alone for easy lookup, preferring kcal over kJ
    # when both exist for the same nutrient (kcal is the more commonly used unit)
    final_totals = {}
    for (name, unit), data in totals.items():
        if name not in final_totals or unit.lower() == "kcal":
            final_totals[name] = {"amount": data["amount"], "unit": unit}

    return final_totals