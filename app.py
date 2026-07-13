from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, render_template_string

from pipeline import process_log
from scorer import score_nutrients, get_flagged_deficiencies
from recommender import get_top_deficiencies, generate_tips

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Nutrition Tracker</title>
<style>
  body { font-family: sans-serif; max-width: 700px; margin: 40px auto; color: #222; }
  h2 { margin-bottom: 4px; }
  .profile-row { display: flex; gap: 12px; margin-bottom: 16px; }
  .profile-row label { font-size: 14px; }
  textarea { width: 100%; padding: 8px; font-size: 14px; }
  button { padding: 8px 16px; margin-top: 8px; cursor: pointer; }
  button:disabled { opacity: 0.6; cursor: default; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
  .status-deficient { color: #b3261e; font-weight: bold; }
  .status-borderline { color: #b06a00; font-weight: bold; }
  .status-adequate { color: #1e7d32; font-weight: bold; }
  .status-excessive { color: #b3261e; font-weight: bold; }
  .status-near_limit { color: #b06a00; font-weight: bold; }
  .status-ok { color: #1e7d32; font-weight: bold; }
  .status-matched { color: #1e7d32; }
  .status-no_confident_match, .status-no_candidates { color: #b3261e; }
  section { margin-top: 28px; }
  .tips { white-space: pre-wrap; background: #f5f5f5; padding: 12px; border-radius: 6px; line-height: 1.5; }
  .hidden { display: none; }
</style>
</head>
<body>
  <h2>Nutrition Tracker</h2>
  <p style="color: #666; font-size: 14px;">Log what you ate and get a nutrient breakdown along with optimization tips.</p>

  <div class="profile-row">
    <div>
      <label for="sex">Sex</label><br>
      <select id="sex">
        <option value="female">Female</option>
        <option value="male">Male</option>
      </select>
    </div>
    <div>
      <label for="age">Age</label><br>
      <input type="number" id="age" value="28" min="19" max="50" style="width: 60px;">
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

  <script>
    async function submitLog() {
        const logText = document.getElementById("logText").value.trim();
        if (!logText) return;

        const sex = document.getElementById("sex").value;
        const age = parseInt(document.getElementById("age").value, 10);
        const btn = document.getElementById("submitBtn");
        const resultsDiv = document.getElementById("results");

        btn.disabled = true;
        btn.textContent = "Analyzing...";
        resultsDiv.classList.add("hidden");

        try {
            const res = await fetch("/process", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ log_text: logText, sex: sex, age: age })
            });

            if (!res.ok) {
                const err = await res.json();
                alert("Error: " + (err.error || "something went wrong"));
                return;
            }

            const data = await res.json();
            renderResults(data);
            resultsDiv.classList.remove("hidden");
        } catch (e) {
            alert("Request failed: " + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = "Analyze";
        }
    }

    function renderResults(data) {
        const itemsBody = document.querySelector("#itemsTable tbody");
        itemsBody.innerHTML = "";
        data.items.forEach(item => {
            const row = document.createElement("tr");
            const statusLabel = item.status === "matched"
                ? "matched: " + item.matched_description
                : item.status.replace(/_/g, " ");
            row.innerHTML = `<td>${item.quantity} ${item.unit} ${item.food_name}</td>
                              <td class="status-${item.status}">${statusLabel}</td>`;
            itemsBody.appendChild(row);
        });

        const nutrientsBody = document.querySelector("#nutrientsTable tbody");
        nutrientsBody.innerHTML = "";
        data.scored_nutrients.forEach(n => {
            const row = document.createElement("tr");
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


@app.route("/process", methods=["POST"])
def process():
    data = request.json
    log_text = data.get("log_text", "").strip()
    sex = data.get("sex", "female")
    age = data.get("age", 28)

    if not log_text:
        return jsonify({"error": "No log text provided"}), 400

    try:
        result = process_log(log_text)
        totals = result["totals"]

        scored = score_nutrients(totals, sex=sex, age=age)
        flagged = get_flagged_deficiencies(scored)
        top_deficiencies = get_top_deficiencies(flagged)

        logged_foods_summary = ", ".join(
            item["food_name"] for item in result["items"] if item["status"] == "matched"
        )
        tips = generate_tips(logged_foods_summary, top_deficiencies) if logged_foods_summary else \
            "No foods were matched, so no recommendations could be generated."

        scored_list = [
            {"name": name, **info} for name, info in scored.items()
        ]

        return jsonify({
            "items": result["items"],
            "scored_nutrients": scored_list,
            "tips": tips,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)