# Nutrition Tracker

A nutrition tracker that takes free-text food logs (e.g. *"I had a chicken
sandwich and a coke"*), parses them into structured food items using an LLM,
matches them against the USDA FoodData Central database to compute a daily
micronutrient profile, scores the result against RDAs to flag likely
deficiencies, and generates personalized, food-based recommendations.

## How it works

```
free-text log
      |
      v
  parser.py  ---------->  LLM extracts structured food items
      |                    [{food_name, quantity, unit}, ...]
      v
  fdc_client.py  ------->  searches USDA FoodData Central for candidates
      |                    (Foundation/SR Legacy first, Branded as fallback)
      v
  matcher.py  ---------->  LLM picks the best-matching candidate,
      |                    given the original log context
      v
  fdc_client.py  ------->  fetches full nutrient profile for the match
      |                    (cached locally in SQLite after first fetch)
      v
  aggregator.py  ------->  converts quantity/unit to grams, scales
      |                    nutrients, sums into daily totals
      v
  scorer.py  ----------->  compares totals against RDA, flags
      |                    deficiencies (< 50% = deficient, 50-80% = borderline)
      v
  recommender.py  ------>  LLM generates food-based tips for the
                           worst 5 flagged deficiencies

  app.py ties all of the above together behind a Flask web page.
```

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   git clone <your-repo-url>
   cd nutrition_tracker
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Get API keys:
   - **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) (used for parsing, matching, and recommendations)
   - **USDA FDC**: [fdc.nal.usda.gov/api-key-signup.html](https://fdc.nal.usda.gov/api-key-signup.html) (free, instant)

4. Copy `.env.example` to `.env` and fill in your real keys:
   ```bash
   cp .env.example .env
   ```

5. Initialize the local nutrient cache:
   ```bash
   python db_setup.py
   ```

6. Run it:
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:5001`.

## Design decisions & tradeoffs

**Why USDA FoodData Central over other nutrition APIs?**
Free, no rate-limit cost, and includes detailed micronutrient data (not just
macros), which most free alternatives don't provide.

**Why Foundation/SR Legacy first, Branded as fallback?**
Foundation and SR Legacy are the cleanest, most standardized entries for
whole/common foods. Branded includes packaged/commercial products (needed
for things like specific sodas or fast food items) but is much larger and
noisier, so it's only searched when the cleaner catalogs return nothing useful.

**Why LLM-based matching instead of pure fuzzy string matching?**
Plain text search on food names often returns technically-valid but
unintuitive matches (e.g. "chicken breast" ranking deli lunchmeat above
plain roasted chicken). An LLM given the original log context can apply
everyday judgement a keyword match can't. Tradeoff: this makes matching
non-deterministic, the same log can occasionally match a different (still
reasonable) candidate on different runs. This is a known, accepted limitation
for v1.

**Why rule-based scoring instead of a trained classifier?**
A simple % of RDA threshold is transparent, requires no training data, and
is easy to reason about and adjust. A scikit-learn classifier is a natural
future upgrade once there's real usage data to train against, not something
that adds value without that data.

**Unit conversion assumptions (known limitations):**
- `"serving"` is treated as a flat 100g, since FDC doesn't reliably provide
  a serving-size-in-grams figure across all foods. This is a rough
  approximation, not a precise conversion.
- Volume units (cup, tbsp, fl_oz, etc.) are converted assuming 1ml ≈ 1g.
  Accurate for water-like liquids (soda, coffee, milk), less accurate for
  dense liquids like honey or oil.
- Raw vs. cooked ambiguity: a logged weight (e.g. "1.33 lb ground beef")
  doesn't specify whether that's raw or cooked weight, and the matcher may
  pick either preparation depending on the run, which changes the nutrient
  profile meaningfully (cooking concentrates nutrients as water content
  drops). Not currently resolved.

**RDA coverage:**
Only two profiles are currently supported: adult male and adult female,
ages 19-50. Pregnancy, lactation, children, and older adults have different
RDAs and are not yet covered.

**Daily totals vs. single-meal logs:**
The scorer compares whatever's logged against a *full day's* RDA. Logging a
single meal will therefore show as "deficient" across most nutrients, that's
expected, not a bug. Meaningful deficiency flags require logging a full
day's intake.

## Known bugs fixed during development (for future reference)

- FDC sometimes lists the same nutrient (e.g. "Energy") twice under
  different unit systems (kcal/kJ) or calculation methods (Atwater General
  vs Specific Factors). Both `fdc_client.py` (dedup on fetch) and
  `aggregator.py` (keying totals by name+unit) guard against this
  double-counting.
- The LLM matcher can occasionally hallucinate an `fdc_id` that isn't
  actually one of the candidates it was given. `matcher.py` validates the
  returned id against the real candidate list before trusting it.

## Tech stack

- **Language**: Python
- **Web framework**: Flask
- **LLM**: OpenAI GPT-5 Nano (parsing, matching, recommendations); Ollama
  (local Gemma models) supported as an alternative for the general chat
  interface groundwork this project was built on
- **Nutrient data**: USDA FoodData Central API
- **Storage**: SQLite (local nutrient cache)

## Roadmap / not yet built

- Multi-day logging and trend tracking
- Expanded RDA coverage (age ranges, pregnancy/lactation)
- Better raw/cooked disambiguation in matching
- Real serving-size data instead of the flat 100g assumption
- ML-based scoring once real usage data exists