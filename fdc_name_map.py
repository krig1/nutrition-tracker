"""
Maps the simplified nutrient names used in RDA_TABLE (for readability)
to USDA FoodData Central's exact nutrient names (used as keys in the
`totals` dict from aggregator.py).

IMPORTANT: every key in RDA_TABLE must have an entry here, or the lookup
in scorer.py will silently miss and report 0 consumed for that nutrient.
"""

FDC_NAME_MAP = {
    "Energy": "Energy",
    "Protein": "Protein",
    "Fiber, total dietary": "Fiber, total dietary",
    "Vitamin C": "Vitamin C, total ascorbic acid",
    "Vitamin A": "Vitamin A, RAE",
    "Vitamin D": "Vitamin D (D2 + D3)",
    "Vitamin E": "Vitamin E (alpha-tocopherol)",
    "Vitamin K": "Vitamin K (phylloquinone)",
    "Vitamin B1": "Thiamin",
    "Vitamin B2": "Riboflavin",
    "Vitamin B3": "Niacin",
    "Vitamin B6": "Vitamin B-6",
    "Vitamin B9": "Folate, total",
    "Vitamin B12": "Vitamin B-12",
    "Calcium": "Calcium, Ca",
    "Iron": "Iron, Fe",
    "Magnesium": "Magnesium, Mg",
    "Zinc": "Zinc, Zn",
    "Potassium": "Potassium, K",
    "Sodium": "Sodium, Na",
}