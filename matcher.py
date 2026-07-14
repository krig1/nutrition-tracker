"""
Uses an LLM to pick the best-matching FDC food from a set of search
candidates, given the original free-text description a person logged.

Why: FDC's plain text search often ranks results in ways that don't
match everyday intuition (e.g. "chicken breast" -> lunchmeat before
plain roasted chicken breast). An LLM with the original context can
usually pick the more sensible match.

Requires: export OPENAI_API_KEY="your-key-here"
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MATCHER_MODEL = "gpt-5.4-mini"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def match_food_llm(logged_description, candidates):
    """
    logged_description: the food item as the user described it,
        e.g. "chicken breast" or "grilled chicken breast"
    candidates: list of dicts from fdc_client.search_food(), e.g.
        [{"fdc_id": 2646170, "description": "Chicken, breast, boneless, skinless, raw", "data_type": "Foundation"}, ...]

    Returns: the chosen fdc_id (int), or None if no candidate is a
    reasonable match.
    """
    if not candidates:
        return None

    candidate_lines = "\n".join(
        f"- fdc_id={c['fdc_id']}: {c['description']} ({c['data_type']})"
        for c in candidates
    )

    prompt = f"""A person logged eating: "{logged_description}"

Here are candidate foods from the USDA FoodData Central database:
{candidate_lines}

Pick the fdc_id that best represents what this person most likely ate.
Assume a normal, everyday interpretation. Prefer plain, minimally-prepared
forms of a food (e.g. "potato, raw" or "potato, baked") over prepared dishes
that happen to contain that food as an ingredient (e.g. "potato pancakes",
"potato salad", "scalloped potatoes"), UNLESS the log specifically names
that dish. The same applies to deli meats, breaded/fried variants, or other
unusual preparations, only pick those if the log implies them.

When a food is logged with no modifier (e.g. "milk", "bread", "cheese",
"rice"), default to the most common, standard version of that food as
typically consumed by the general population, not a specialized,
alternative, or niche variant. For example, unmodified "milk" should
default to dairy cow's milk (whole or 2%), not rice milk, almond milk,
oat milk, goat milk, or any other plant-based or specialty substitute.
Only pick a non-default variant if the log names it directly (e.g. "oat
milk", "almond milk", "skim milk").

Default to the standard adult/general-population version of a food. Do NOT
pick infant, toddler, baby food, medical/enteral, or other specialized-
population variants (e.g. "Babyfood, potatoes, toddler", "Formula, infant")
unless the log explicitly mentions a baby, toddler, or medical context.
Likewise avoid novelty, fortified, or diet-specific variants (e.g. "potato,
puffs, imitation", "potato, dehydrated, flakes") unless implied by the log.

Respond with ONLY a JSON object in this exact format, no other text:
{{"fdc_id": <number or null>, "reason": "<one short sentence>"}}

Use null for fdc_id only if none of the candidates are a reasonable match."""

    client = _get_client()
    response = client.chat.completions.create(
        model=MATCHER_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()

    # Models sometimes wrap JSON in markdown fences despite instructions; strip if present
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    chosen_id = parsed.get("fdc_id")
    if chosen_id is None:
        return None

    # Guard against hallucinated fdc_ids: only trust it if it's actually
    # one of the candidates we gave the model.
    valid_ids = {c["fdc_id"] for c in candidates}
    if chosen_id not in valid_ids:
        return None

    return chosen_id