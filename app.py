from dotenv import load_dotenv
load_dotenv()

import threading
import uuid

from flask import Flask, request, jsonify, render_template_string

from pipeline import process_log
from scorer import score_nutrients, get_flagged_deficiencies
from recommender import get_top_deficiencies, generate_tips

app = Flask(__name__)

# In-memory job store for progress polling. Fine for a single-process local
# dev app; would need a real store (Redis, DB) behind multiple workers/gunicorn.
_jobs = {}
_jobs_lock = threading.Lock()

PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Nutrition Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #211c2c;
    --bg-elevated: #2b2538;
    --bg-card: #332c43;
    --border: #473e5c;
    --border-hover: #5f5477;
    --text-primary: #ffffff;
    --text-secondary: #cbc2de;
    --text-muted: #948aab;
    --accent: #ff8a7d;
    --accent-hover: #ffa89d;
    --accent-soft: rgba(255, 138, 125, 0.2);
    --accent2: #86edff;
    --accent3: #c7a3ff;
    --deficient: #ff8a7d;
    --borderline: #ffcb80;
    --adequate: #7ef5bb;
  }

  * { box-sizing: border-box; }

  body {
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text-primary);
    max-width: 680px;
    margin: 0 auto;
    padding: 64px 24px 100px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    position: relative;
    overflow-x: hidden;
  }

  body::before, body::after {
    content: "";
    position: fixed;
    width: 520px;
    height: 520px;
    border-radius: 50%;
    filter: blur(110px);
    z-index: -1;
    opacity: 0.6;
    pointer-events: none;
  }

  body::before {
    top: -180px;
    left: -160px;
    background: radial-gradient(circle, var(--accent), transparent 70%);
    animation: float1 14s ease-in-out infinite;
  }

  body::after {
    bottom: -200px;
    right: -180px;
    background: radial-gradient(circle, var(--accent2), transparent 70%);
    animation: float2 16s ease-in-out infinite;
  }

  .blob3 {
    content: "";
    position: fixed;
    top: 30%;
    right: -140px;
    width: 380px;
    height: 380px;
    border-radius: 50%;
    filter: blur(100px);
    z-index: -1;
    opacity: 0.45;
    background: radial-gradient(circle, var(--accent3), transparent 70%);
    animation: float3 18s ease-in-out infinite;
    pointer-events: none;
  }

  @keyframes float1 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(60px, 40px) scale(1.15); }
  }

  @keyframes float2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(-50px, -30px) scale(1.1); }
  }

  @keyframes float3 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(-40px, 50px) scale(1.2); }
  }

  h2 {
    font-family: "Space Grotesk", "Inter", sans-serif;
    margin: 0 0 6px;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: -0.01em;
    background: linear-gradient(120deg, #ffffff 20%, var(--accent) 65%, var(--accent3) 110%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }

  h3 {
    font-family: "Space Grotesk", "Inter", sans-serif;
    font-weight: 600;
    font-size: 12px;
    color: var(--text-secondary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0 0 14px;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
    margin-top: 0;
    margin-bottom: 32px;
  }

  .profile-row {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
  }

  .field {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    transition: border-color 0.15s ease;
  }

  .field:hover { border-color: var(--border-hover); }

  .profile-row label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    display: block;
    margin-bottom: 4px;
  }

  select, input[type="number"] {
    font-family: inherit;
    background: transparent;
    border: none;
    color: var(--text-primary);
    padding: 0;
    font-size: 14px;
    width: 100%;
  }

  select:focus, input:focus, textarea:focus {
    outline: none;
  }

  textarea {
    width: 100%;
    padding: 14px 16px;
    font-size: 14px;
    font-family: inherit;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    resize: vertical;
    margin-top: 12px;
    transition: border-color 0.15s ease;
  }

  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--text-muted); }

  button {
    font-family: "Space Grotesk", "Inter", sans-serif;
    padding: 10px 20px;
    margin-top: 14px;
    min-width: 210px;
    text-align: center;
    cursor: pointer;
    background: linear-gradient(120deg, var(--accent), var(--accent3));
    color: #1a1015;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: -0.01em;
    box-shadow: 0 4px 24px rgba(255, 122, 107, 0.35), 0 0 40px rgba(185, 140, 255, 0.15);
    transition: background 0.15s ease, transform 0.05s ease, box-shadow 0.15s ease;
  }

  button:hover:not(:disabled) {
    box-shadow: 0 6px 30px rgba(255, 122, 107, 0.5), 0 0 50px rgba(185, 140, 255, 0.25);
    transform: translateY(-1px);
  }
  button:active:not(:disabled) { transform: scale(0.98); }

  button:disabled {
    opacity: 0.75;
    cursor: default;
    box-shadow: none;
    animation: pulseText 1.4s ease-in-out infinite;
  }

  @keyframes pulseText {
    0%, 100% { opacity: 0.75; }
    50% { opacity: 0.5; }
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }

  th {
    text-align: left;
    padding: 8px 10px;
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    border-bottom: 1px solid var(--border);
  }

  td {
    text-align: left;
    padding: 11px 10px;
    border-bottom: 1px solid var(--border);
    color: var(--text-primary);
  }

  tr:last-child td { border-bottom: none; }

  tbody tr {
    opacity: 0;
    animation: rowIn 0.4s ease forwards;
  }

  @keyframes rowIn {
    from { opacity: 0; transform: translateX(-6px); }
    to { opacity: 1; transform: translateX(0); }
  }

  .status-deficient { color: var(--deficient); font-weight: 600; }
  .status-borderline { color: var(--borderline); font-weight: 600; }
  .status-adequate { color: var(--adequate); font-weight: 600; }
  .status-excessive { color: var(--deficient); font-weight: 600; }
  .status-near_limit { color: var(--borderline); font-weight: 600; }
  .status-ok { color: var(--adequate); font-weight: 600; }
  .status-matched { color: var(--text-secondary); }
  .status-no_confident_match, .status-no_candidates, .status-no_nutrient_data { color: var(--deficient); }

  section {
    margin-top: 28px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 22px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  section:hover {
    border-color: var(--border-hover);
    box-shadow: 0 0 30px rgba(255, 122, 107, 0.06);
  }

  .tips {
    white-space: pre-wrap;
    line-height: 1.65;
    font-size: 13.5px;
    color: var(--text-primary);
  }

  .hidden { display: none; }

  .sources {
    margin-top: 48px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }

  .sources-heading {
    font-family: "Space Grotesk", "Inter", sans-serif;
    font-weight: 600;
    font-size: 12px;
    color: var(--text-secondary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0 0 12px;
  }

  .sources-intro {
    margin: 0 0 14px;
    font-size: 12.5px;
    line-height: 1.6;
    color: var(--text-muted);
  }

  .sources-details {
    font-size: 12.5px;
  }

  .sources-details + .sources-details {
    margin-top: 4px;
    border-top: 1px solid var(--border);
    padding-top: 4px;
  }

  .sources-details summary {
    cursor: pointer;
    list-style: none;
    font-family: "Space Grotesk", "Inter", sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-secondary);
    padding: 6px 0;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: color 0.15s ease;
  }

  .sources-details summary::-webkit-details-marker { display: none; }

  .sources-details summary::before {
    content: "›";
    display: inline-block;
    font-size: 14px;
    transition: transform 0.2s ease;
    color: var(--accent);
  }

  .sources-details[open] summary::before {
    transform: rotate(90deg);
  }

  .sources-details summary:hover {
    color: var(--text-primary);
  }

  .sources-body {
    margin-top: 10px;
    padding-left: 4px;
    border-left: 2px solid var(--border);
    padding-left: 14px;
  }

  .sources-body p {
    margin: 0 0 10px;
    line-height: 1.6;
    color: var(--text-muted);
  }

  .sources-body p:last-child { margin-bottom: 0; }

  .sources a {
    color: var(--accent2);
    text-decoration: none;
    border-bottom: 1px solid rgba(134, 237, 255, 0.35);
    transition: border-color 0.15s ease;
  }

  .sources a:hover {
    border-color: var(--accent2);
  }

  #results {
    opacity: 0;
    transform: translateY(6px);
  }

  #results.show {
    animation: fadeIn 0.35s ease forwards;
  }

  @keyframes fadeIn {
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
</head>
<body>
  <div class="blob3"></div>
  <h2>Nutrition Tracker</h2>
  <p class="subtitle">Log what you ate (be specific!) and get a nutrient breakdown along with optimization tips.</p>

  <div class="profile-row">
    <div class="field" style="flex: 1;">
      <label for="sex">Sex</label>
      <select id="sex">
        <option value="female">Female</option>
        <option value="male">Male</option>
      </select>
    </div>
    <div class="field" style="width: 100px;">
      <label for="age">Age</label>
      <input type="number" id="age" value="28" min="19" max="50">
    </div>
  </div>

  <textarea id="logText" rows="3" placeholder="Example: I had a chicken sandwich and a coke"></textarea><br>
  <button id="submitBtn" onclick="submitLog()">Analyze</button>

  <div id="results" class="hidden">
    <section>
      <h3>Items</h3>
      <table id="itemsTable"><tbody></tbody></table>
    </section>

    <section>
      <h3>Nutrient Status</h3>
      <table id="nutrientsTable">
        <thead><tr><th>Nutrient</th><th>Consumed</th><th>RDA</th><th>%RDA</th><th>Status</th></tr></thead>
        <tbody></tbody>
      </table>
    </section>

    <section>
      <h3>Recommendations</h3>
      <div id="tips" class="tips"></div>
    </section>
  </div>

  <footer class="sources">
    <h3 class="sources-heading">Sources</h3>

    <p class="sources-intro">
      Food logs are parsed and matched using AI, results are estimates and
      may not reflect exact products or preparations. RDA values reflect
      general adult guidelines and are not personalized medical advice.
    </p>

    <details class="sources-details">
      <summary>Where the nutrient data comes from</summary>
      <div class="sources-body">
        <p>
          Food and nutrient values come from
          <a href="https://fdc.nal.usda.gov/" target="_blank" rel="noopener">USDA FoodData Central</a>,
          searched via its public API. Matches are pulled from the Foundation
          and SR Legacy datasets first, falling back to Branded data only when
          nothing else matches confidently.
        </p>
        <p>
          Because logs are free text, matching to a specific FDC entry is done
          by AI and is inherently approximate, results may not reflect the
          exact preparation, brand, or cut you actually ate.
        </p>
      </div>
    </details>

    <details class="sources-details">
      <summary>Where the RDA values come from</summary>
      <div class="sources-body">
        <p>
          Most vitamin, mineral, protein, and fiber targets come from the
          <a href="https://www.ncbi.nlm.nih.gov/books/NBK208874/" target="_blank" rel="noopener">National Academies' Dietary Reference Intakes (2003)</a>,
          specifically the vitamin, element, and macronutrient reference tables.
        </p>
        <p>
          Potassium and sodium use the updated
          <a href="https://www.ncbi.nlm.nih.gov/books/NBK587683/" target="_blank" rel="noopener">2019 DRI for Sodium and Potassium</a>,
          which supersedes the older 2005 values (Adequate Intake for potassium,
          Chronic Disease Risk Reduction Intake for sodium).
        </p>
        <p>
          Sex-specific values for iron, zinc, vitamin A, vitamin K, and potassium
          were cross-checked against individual National Academies nutrient
          reports and the
          <a href="https://lpi.oregonstate.edu/mic/minerals/potassium" target="_blank" rel="noopener">Linus Pauling Institute</a>.
        </p>
        <p>
          Calorie targets (2500 kcal male / 2000 kcal female) are a commonly-used
          general estimate, not an official DRI/RDA value, since energy needs
          vary by individual activity level. This is flagged in the code as a
          known limitation.
        </p>
        <p>
          The FDA's Daily Value table was considered as a simpler,
          single-population alternative but wasn't used, since sex-specific
          personalization is central to this app's deficiency detection.
        </p>
      </div>
    </details>
  </footer>

  <script>
    async function submitLog() {
        const logText = document.getElementById("logText").value.trim();
        if (!logText) return;

        const sex = document.getElementById("sex").value;
        const age = parseInt(document.getElementById("age").value, 10);
        const btn = document.getElementById("submitBtn");
        const resultsDiv = document.getElementById("results");

        btn.disabled = true;
        btn.textContent = "Starting...";
        resultsDiv.classList.add("hidden");
        resultsDiv.classList.remove("show");

        try {
            const startRes = await fetch("/process/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ log_text: logText, sex: sex, age: age })
            });

            if (!startRes.ok) {
                const err = await startRes.json();
                alert("Error: " + (err.error || "something went wrong"));
                return;
            }

            const { job_id } = await startRes.json();

            const data = await pollJob(job_id, btn);
            if (data.error) {
                alert("Error: " + data.error);
                return;
            }

            renderResults(data);
            resultsDiv.classList.remove("hidden");
            requestAnimationFrame(() => resultsDiv.classList.add("show"));
        } catch (e) {
            alert("Request failed: " + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Analyze";
        }
    }

    function pollJob(jobId, btn) {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const res = await fetch(`/process/status/${jobId}`);
                    if (!res.ok) {
                        reject(new Error("Lost track of the job status"));
                        return;
                    }
                    const status = await res.json();

                    if (status.stage) {
                        btn.textContent = status.stage;
                    }

                    if (status.done) {
                        resolve(status.error ? { error: status.error } : status.result);
                        return;
                    }

                    setTimeout(poll, 400);
                } catch (e) {
                    reject(e);
                }
            };
            poll();
        });
    }

    function renderResults(data) {
        const itemsBody = document.querySelector("#itemsTable tbody");
        itemsBody.innerHTML = "";
        data.items.forEach((item, i) => {
            const row = document.createElement("tr");
            row.style.animationDelay = (i * 0.05) + "s";
            const statusLabel = item.status === "matched"
                ? "matched: " + item.matched_description
                : item.status.replace(/_/g, " ");
            row.innerHTML = `<td>${item.quantity} ${item.unit} ${item.food_name}</td>
                              <td class="status-${item.status}">${statusLabel}</td>`;
            itemsBody.appendChild(row);
        });

        const nutrientsBody = document.querySelector("#nutrientsTable tbody");
        nutrientsBody.innerHTML = "";
        data.scored_nutrients.forEach((n, i) => {
            const row = document.createElement("tr");
            row.style.animationDelay = (i * 0.05) + "s";
            row.innerHTML = `<td>${n.name}</td>
                              <td>${n.consumed_amount}${n.unit}</td>
                              <td>${n.rda_amount}${n.unit}</td>
                              <td>${n.percent_of_rda}%</td>
                              <td class="status-${n.status}">${n.status}</td>`;
            nutrientsBody.appendChild(row);
        });

        document.getElementById("tips").textContent = data.tips;
    }
  </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE)


def _run_job(job_id, log_text, sex, age):
    def on_progress(stage_msg):
        with _jobs_lock:
            _jobs[job_id]["stage"] = stage_msg

    try:
        result = process_log(log_text, on_progress=on_progress)
        totals = result["totals"]

        with _jobs_lock:
            _jobs[job_id]["stage"] = "Scoring against your RDA..."

        scored = score_nutrients(totals, sex=sex, age=age)
        flagged = get_flagged_deficiencies(scored)
        top_deficiencies = get_top_deficiencies(flagged)

        logged_foods_summary = ", ".join(
            item["food_name"] for item in result["items"] if item["status"] == "matched"
        )

        if logged_foods_summary:
            with _jobs_lock:
                _jobs[job_id]["stage"] = "Generating recommendations..."
            tips = generate_tips(logged_foods_summary, top_deficiencies)
        else:
            tips = "No foods were matched, so no recommendations could be generated."

        scored_list = [
            {"name": name, **info} for name, info in scored.items()
        ]

        with _jobs_lock:
            _jobs[job_id]["done"] = True
            _jobs[job_id]["result"] = {
                "items": result["items"],
                "scored_nutrients": scored_list,
                "tips": tips,
            }

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["done"] = True
            _jobs[job_id]["error"] = str(e)


@app.route("/process/start", methods=["POST"])
def process_start():
    data = request.json
    log_text = data.get("log_text", "").strip()
    sex = data.get("sex", "female")
    age = data.get("age", 28)

    if not log_text:
        return jsonify({"error": "No log text provided"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"stage": "Starting...", "done": False, "result": None, "error": None}

    thread = threading.Thread(target=_run_job, args=(job_id, log_text, sex, age), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/process/status/<job_id>", methods=["GET"])
def process_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Unknown job_id"}), 404

        response = {
            "stage": job["stage"],
            "done": job["done"],
        }
        if job["done"]:
            response["result"] = job["result"]
            response["error"] = job["error"]
            # Job consumed, clean up so the store doesn't grow unbounded.
            del _jobs[job_id]

        return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=5001)