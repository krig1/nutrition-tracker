"""
Compares daily nutrient totals (from aggregator.py) against RDA values
and flags likely deficiencies.

Scoring bands (v1, simple rule-based thresholds):
  < 50% of RDA  -> "deficient"
  50-80% of RDA -> "borderline"
  >= 80% of RDA -> "adequate"

For upper-limit nutrients (currently just Sodium), the logic flips:
  > 100% of limit -> "excessive"
  70-100%         -> "near_limit"
  < 70%            -> "ok"

IMPORTANT: RDA_TABLE keys are simplified display names (e.g. "Vitamin C"),
but `totals` (from aggregator.py) is keyed using USDA FDC's exact nutrient
names (e.g. "Vitamin C, total ascorbic acid"). fdc_name_map.FDC_NAME_MAP
bridges the two, every RDA_TABLE key must have an entry there or the
lookup will silently return 0.
"""
from rda_data import get_rda_profile, UPPER_LIMIT_NUTRIENTS
from fdc_name_map import FDC_NAME_MAP

DEFICIENT_THRESHOLD = 0.5
BORDERLINE_THRESHOLD = 0.8

NEAR_LIMIT_THRESHOLD = 0.7


def score_nutrients(totals, sex, age):
    """
    totals: dict from aggregator.compute_daily_totals(), keyed by FDC's
        exact nutrient names, e.g. {"Vitamin C, total ascorbic acid": {...}}
    sex: "male" or "female"
    age: int

    Returns: dict of {display_name: {rda_amount, unit, consumed_amount,
        percent_of_rda, status}}, only for nutrients we have an RDA for.
    """
    rda_profile = get_rda_profile(sex, age)
    results = {}

    for display_name, rda_info in rda_profile.items():
        fdc_name = FDC_NAME_MAP.get(display_name)
        if fdc_name is None:
            raise KeyError(
                f"'{display_name}' is in RDA_TABLE but missing from "
                f"FDC_NAME_MAP in fdc_name_map.py. Add a mapping entry."
            )

        consumed = totals.get(fdc_name)
        consumed_amount = consumed["amount"] if consumed else 0.0
        rda_amount = rda_info["amount"]
        unit = rda_info["unit"]

        percent = (consumed_amount / rda_amount) * 100 if rda_amount else 0.0

        if display_name in UPPER_LIMIT_NUTRIENTS:
            status = _score_upper_limit(percent)
        else:
            status = _score_minimum_target(percent)

        results[display_name] = {
            "rda_amount": rda_amount,
            "unit": unit,
            "consumed_amount": round(consumed_amount, 2),
            "percent_of_rda": round(percent, 1),
            "status": status,
        }

    return results


def _score_minimum_target(percent):
    if percent < DEFICIENT_THRESHOLD * 100:
        return "deficient"
    if percent < BORDERLINE_THRESHOLD * 100:
        return "borderline"
    return "adequate"


def _score_upper_limit(percent):
    if percent > 100:
        return "excessive"
    if percent >= NEAR_LIMIT_THRESHOLD * 100:
        return "near_limit"
    return "ok"


def get_flagged_deficiencies(scored_results):
    """
    Convenience filter: returns only nutrients flagged as deficient
    or borderline (the ones worth generating recommendations for).
    """
    return {
        name: info for name, info in scored_results.items()
        if info["status"] in ("deficient", "borderline")
    }