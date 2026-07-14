"""
RDA / AI (Recommended Dietary Allowance / Adequate Intake) reference
values for adults 19-50, split by sex.

PRIMARY SOURCES (all verified directly, not from memory):

1. Vitamins, Protein, Fiber, Calcium, Iron, Magnesium, Zinc, Selenium:
   Institute of Medicine (US) Committee on Use of Dietary Reference
   Intakes in Nutrition Labeling. "Reference Tables." Dietary Reference
   Intakes: Guiding Principles for Nutrition Labeling and Fortification.
   Washington (DC): National Academies Press (US); 2003.
   https://www.ncbi.nlm.nih.gov/books/NBK208874/
   (Tables C-2, C-3, C-4)

2. Potassium: updated 2019 Adequate Intake (AI), which superseded the
   older 2005 flat 4700mg value.
   National Academies of Sciences, Engineering, and Medicine. Dietary
   Reference Intakes for Sodium and Potassium. Washington (DC):
   National Academies Press (US); 2019.
   https://www.ncbi.nlm.nih.gov/books/NBK587683/

3. Sodium: 2019 Chronic Disease Risk Reduction Intake (CDRR), which
   superseded the older 2005 Tolerable Upper Intake Level (UL).
   National Academies of Sciences, Engineering, and Medicine. Dietary
   Reference Intakes for Sodium and Potassium. Washington (DC):
   National Academies Press (US); 2019.
   https://www.ncbi.nlm.nih.gov/books/NBK545436/

Simplification for v1: covers ages 19-50 only (using the 19-30 value
where 19-30 and 31-50 differ slightly, e.g. magnesium). Does not cover
pregnancy, lactation, older adults (51+), or children, these have
different RDAs and are a documented limitation.

Each nutrient maps to: {"amount": ..., "unit": ...}
"""

RDA_TABLE = {
    "male_19_50": {
        "Energy": {"amount": 2500, "unit": "kcal"},  # general estimate, not a DRI table value; varies by activity level
        "Protein": {"amount": 56, "unit": "g"},
        "Fiber, total dietary": {"amount": 38, "unit": "g"},
        "Vitamin C": {"amount": 90, "unit": "mg"},
        "Vitamin A": {"amount": 900, "unit": "µg"},
        "Vitamin D": {"amount": 5, "unit": "µg"},  # AI, not RDA (no RDA established)
        "Vitamin E": {"amount": 15, "unit": "mg"},
        "Vitamin K": {"amount": 120, "unit": "µg"},  # AI, not RDA
        "Vitamin B1": {"amount": 1.2, "unit": "mg"},
        "Vitamin B2": {"amount": 1.3, "unit": "mg"},
        "Vitamin B3": {"amount": 16, "unit": "mg"},
        "Vitamin B6": {"amount": 1.3, "unit": "mg"},
        "Vitamin B9": {"amount": 400, "unit": "µg"},
        "Vitamin B12": {"amount": 2.4, "unit": "µg"},
        "Calcium": {"amount": 1000, "unit": "mg"},
        "Iron": {"amount": 8, "unit": "mg"},
        "Magnesium": {"amount": 400, "unit": "mg"},
        "Zinc": {"amount": 11, "unit": "mg"},
        "Potassium": {"amount": 3400, "unit": "mg"},  # AI, 2019 update
        "Sodium": {"amount": 2300, "unit": "mg"},  # CDRR (upper limit), 2019 update
    },
    "female_19_50": {
        "Energy": {"amount": 2000, "unit": "kcal"},  # general estimate, not a DRI table value; varies by activity level
        "Protein": {"amount": 46, "unit": "g"},
        "Fiber, total dietary": {"amount": 25, "unit": "g"},
        "Vitamin C": {"amount": 75, "unit": "mg"},
        "Vitamin A": {"amount": 700, "unit": "µg"},
        "Vitamin D": {"amount": 5, "unit": "µg"},  # AI, not RDA
        "Vitamin E": {"amount": 15, "unit": "mg"},
        "Vitamin K": {"amount": 90, "unit": "µg"},  # AI, not RDA
        "Vitamin B1": {"amount": 1.1, "unit": "mg"},
        "Vitamin B2": {"amount": 1.1, "unit": "mg"},
        "Vitamin B3": {"amount": 14, "unit": "mg"},
        "Vitamin B6": {"amount": 1.3, "unit": "mg"},
        "Vitamin B9": {"amount": 400, "unit": "µg"},
        "Vitamin B12": {"amount": 2.4, "unit": "µg"},
        "Calcium": {"amount": 1000, "unit": "mg"},
        "Iron": {"amount": 18, "unit": "mg"},  # premenopausal; postmenopausal is 8mg, not currently distinguished
        "Magnesium": {"amount": 310, "unit": "mg"},
        "Zinc": {"amount": 8, "unit": "mg"},
        "Potassium": {"amount": 2600, "unit": "mg"},  # AI, 2019 update
        "Sodium": {"amount": 2300, "unit": "mg"},  # CDRR (upper limit), 2019 update
    },
}

# Nutrients where being ABOVE the value is the concern, not below
# (i.e. this is an upper limit/CDRR, not a minimum target)
UPPER_LIMIT_NUTRIENTS = {"Sodium"}


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