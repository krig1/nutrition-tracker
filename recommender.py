"""
Generates personalized, food-based recommendations for the most
significant nutrient deficiencies, grounded in what the person already
ate (so suggestions are specific, not generic "eat more vegetables").

Requires: export OPENAI_API_KEY="your-key-here" (or via .env)
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

RECOMMENDER_MODEL = "gpt-5.4-nano"
TOP_N_DEFICIENCIES = 5

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def get_top_deficiencies(flagged_deficiencies, n=TOP_N_DEFICIENCIES):
    """
    flagged_deficiencies: dict from scorer.get_flagged_deficiencies()

    Returns the n worst (lowest %RDA) as a list of (name, info) tuples,
    sorted worst-first.
    """
    sorted_items = sorted(
        flagged_deficiencies.items(),
        key=lambda pair: pair[1]["percent_of_rda"]
    )
    return sorted_items[:n]


def generate_tips(logged_foods_summary, top_deficiencies):
    """
    logged_foods_summary: short string describing what was logged,
        e.g. "chicken sandwich, coca-cola"
    top_deficiencies: list of (nutrient_name, info) tuples, as returned
        by get_top_deficiencies()

    Returns: a string with 2-3 specific, food-based tips.
    """
    if not top_deficiencies:
        return "No significant deficiencies flagged, nutrient intake looks solid for what was logged."

    deficiency_lines = "\n".join(
        f"- {name}: {info['consumed_amount']}{info['unit']} consumed vs {info['rda_amount']}{info['unit']} RDA "
        f"({info['percent_of_rda']}% of daily target, status: {info['status']})"
        for name, info in top_deficiencies
    )

    prompt = f"""A person logged eating: {logged_foods_summary}

Based on their day's intake so far, these nutrients are notably low relative to their daily targets:
{deficiency_lines}

Give 2-3 specific, food-based suggestions to help close these gaps for the rest of the day.
Requirements:
- Name actual foods (e.g. "a cup of spinach" or "a handful of almonds"), not vague advice like "eat more vegetables"
- Prefer foods that address multiple flagged nutrients at once where possible
- Keep it brief and practical, a couple sentences per suggestion
- Do not invent nutrient numbers, only use what's given above as context

Respond in plain text, no markdown headers, just the suggestions."""

    client = _get_client()
    response = client.chat.completions.create(
        model=RECOMMENDER_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()