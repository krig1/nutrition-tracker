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
"""
from rda_data import get_rda_profile, UPPER_LIMIT_NUTRIENTS

DEFICIENT_THRESHOLD = 0.5
BORDERLINE_THRESHOLD = 0.8

NEAR_LIMIT_THRESHOLD = 0.7


def score_nutrients(totals, sex, age):
    """
    totals: dict from aggregator.compute_daily_totals(), e.g.
        {"Protein": {"amount": 16.28, "unit": "g"}, ...}
    sex: "male" or "female"
    age: int

    Returns: dict of {nutrient_name: {rda_amount, unit, consumed_amount,
        percent_of_rda, status}}, only for nutrients we have an RDA for.
    """
    rda_profile = get_rda_profile(sex, age)
    results = {}

    for nutrient_name, rda_info in rda_profile.items():
        consumed = totals.get(nutrient_name)
        consumed_amount = consumed["amount"] if consumed else 0.0
        rda_amount = rda_info["amount"]
        unit = rda_info["unit"]

        percent = (consumed_amount / rda_amount) * 100 if rda_amount else 0.0

        if nutrient_name in UPPER_LIMIT_NUTRIENTS:
            status = _score_upper_limit(percent)
        else:
            status = _score_minimum_target(percent)

        results[nutrient_name] = {
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