"""
RDA (Recommended Dietary Allowance) reference values.

Source: NIH Office of Dietary Supplements / USDA published RDA tables.
Covers adults 19-50, the most common case for a v1. Values are per day.

Simplification for v1: only two profiles (adult male, adult female,
ages 19-50). Does not cover pregnancy, lactation, older adults, or
children, these have different RDAs and are a documented limitation.

Each nutrient maps to: {"amount": ..., "unit": ...}
"""

RDA_TABLE = {
    "male_19_50": {
        "Energy": {"amount": 2500, "unit": "kcal"},  # rough estimate, varies by activity
        "Protein": {"amount": 56, "unit": "g"},
        "Fiber, total dietary": {"amount": 38, "unit": "g"},
        "Vitamin C, total ascorbic acid": {"amount": 90, "unit": "mg"},
        "Vitamin A, RAE": {"amount": 900, "unit": "µg"},
        "Vitamin D (D2 + D3)": {"amount": 20, "unit": "µg"},
        "Vitamin E (alpha-tocopherol)": {"amount": 15, "unit": "mg"},
        "Vitamin K (phylloquinone)": {"amount": 120, "unit": "µg"},
        "Thiamin": {"amount": 1.2, "unit": "mg"},
        "Riboflavin": {"amount": 1.3, "unit": "mg"},
        "Niacin": {"amount": 16, "unit": "mg"},
        "Vitamin B-6": {"amount": 1.3, "unit": "mg"},
        "Folate, total": {"amount": 400, "unit": "µg"},
        "Vitamin B-12": {"amount": 2.4, "unit": "µg"},
        "Calcium, Ca": {"amount": 1000, "unit": "mg"},
        "Iron, Fe": {"amount": 8, "unit": "mg"},
        "Magnesium, Mg": {"amount": 400, "unit": "mg"},
        "Zinc, Zn": {"amount": 11, "unit": "mg"},
        "Potassium, K": {"amount": 3400, "unit": "mg"},
        "Sodium, Na": {"amount": 2300, "unit": "mg"},  # upper limit, not a target minimum
    },
    "female_19_50": {
        "Energy": {"amount": 2000, "unit": "kcal"},
        "Protein": {"amount": 46, "unit": "g"},
        "Fiber, total dietary": {"amount": 25, "unit": "g"},
        "Vitamin C, total ascorbic acid": {"amount": 75, "unit": "mg"},
        "Vitamin A, RAE": {"amount": 700, "unit": "µg"},
        "Vitamin D (D2 + D3)": {"amount": 20, "unit": "µg"},
        "Vitamin E (alpha-tocopherol)": {"amount": 15, "unit": "mg"},
        "Vitamin K (phylloquinone)": {"amount": 90, "unit": "µg"},
        "Thiamin": {"amount": 1.1, "unit": "mg"},
        "Riboflavin": {"amount": 1.1, "unit": "mg"},
        "Niacin": {"amount": 14, "unit": "mg"},
        "Vitamin B-6": {"amount": 1.3, "unit": "mg"},
        "Folate, total": {"amount": 400, "unit": "µg"},
        "Vitamin B-12": {"amount": 2.4, "unit": "µg"},
        "Calcium, Ca": {"amount": 1000, "unit": "mg"},
        "Iron, Fe": {"amount": 18, "unit": "mg"},  # higher due to menstruation
        "Magnesium, Mg": {"amount": 310, "unit": "mg"},
        "Zinc, Zn": {"amount": 8, "unit": "mg"},
        "Potassium, K": {"amount": 2600, "unit": "mg"},
        "Sodium, Na": {"amount": 2300, "unit": "mg"},  # upper limit, not a target minimum
    },
}

# Nutrients where being ABOVE the value is the concern, not below
# (i.e. this is an upper limit, not a minimum target)
UPPER_LIMIT_NUTRIENTS = {"Sodium, Na"}


def get_rda_profile(sex, age):
    """
    sex: "male" or "female"
    age: int

    Returns the RDA dict for the closest matching profile.
    v1 only supports ages 19-50; outside that range, falls back to
    the 19-50 table with a caveat (documented limitation).
    """
    key = f"{sex.lower()}_19_50"
    if key not in RDA_TABLE:
        raise ValueError(f"No RDA profile for sex='{sex}'")
    return RDA_TABLE[key]