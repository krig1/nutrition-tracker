"""
Parses free-text food logs (e.g. "I had a chicken sandwich and a coke")
into structured food items: [{food_name, quantity, unit}, ...]

This structured output is what gets fed into matcher.py to find the
corresponding USDA FDC entries.

Requires: export OPENAI_API_KEY="your-key-here" (or via .env)
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PARSER_MODEL = "gpt-5.4-nano"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


PARSE_PROMPT_TEMPLATE = """Parse the following food log into a list of individual food items.

Food log: "{log_text}"

For each distinct food or drink item mentioned, extract:
- food_name: a short, generic name for the food (e.g. "chicken sandwich", "coca-cola", "banana")
- quantity: a number representing how much (default to 1 if not specified)
- unit: the unit of measurement, using EXACTLY the unit the person mentioned,
  do not convert it yourself. Valid units: g, kg, oz, lb, cup, tbsp, tsp, fl_oz, serving.
  If the person gives a weight/volume (e.g. "1.33 lb", "6 oz", "2 cups"), keep
  that exact number and unit, do not convert to a different unit.
  Use "serving" only for whole/countable items with no stated weight/volume
  (e.g. 1 sandwich, 1 banana, 2 eggs).
  If a common item's size is implied but not stated (e.g. "a coke", "a coffee"),
  make a reasonable default assumption using one of the valid units above
  (e.g. a can of coke = 12 fl_oz) rather than leaving it blank.

Respond with ONLY a JSON array in this exact format, no other text, no markdown fences:
[{{"food_name": "...", "quantity": <number>, "unit": "..."}}, ...]

If the log mentions no identifiable food or drink, respond with an empty array: []"""


def parse_log(log_text):
    """
    log_text: free-text description of what someone ate, e.g.
        "I had a chicken sandwich and a coke"

    Returns: list of dicts, e.g.
        [{"food_name": "chicken sandwich", "quantity": 1, "unit": "serving"},
         {"food_name": "coca-cola", "quantity": 12, "unit": "fl_oz"}]
    """
    prompt = PARSE_PROMPT_TEMPLATE.format(log_text=log_text)

    client = _get_client()
    response = client.chat.completions.create(
        model=PARSER_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if the model adds them despite instructions
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse model output as JSON:\n{raw}")

    if not isinstance(parsed, list):
        raise ValueError(f"Expected a JSON array, got: {type(parsed)}")

    return parsed