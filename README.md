# 💧 Drinking Water Quality Advisor - Expert System

A rule-based **expert system** (Python + Streamlit) that diagnoses household drinking-water problems and
advises what to do. Built for the CUSIT AI major assignment.

| Requirement | Where it is met |
|---|---|
| Knowledge base: **100 rules** | `rules.py` (R01-R100) |
| Knowledge base: **300 assertions** | `assertions.py` (129 observations + 171 derived = 300) |
| **Inference engine** | `engine.py` - forward chaining, 2 stages, reasoning trace, follow-up questions |
| **Natural-language interface** | `nlp.py` + `app.py` - free-text chat, negation, lab-number parsing, yes/no dialogue |

## How it works
1. **Assertions** are facts. *Observations* are reported by the user (colour, smell, source, lab values,
   symptoms, who drinks the water). *Derived* assertions are concluded by rules: findings (40), risk
   levels (6), likely causes (24) and recommended actions (101).
2. **Rules** are `IF all(...) AND any(...) AND NOT(...) THEN conclusions`.
3. The **engine** repeats "find a rule whose conditions hold -> add its conclusions" until nothing new is
   added (forward chaining). Stage 2 runs last for rules that need "no hazards were found". It records every
   rule fired, ranks risk (low -> critical) and orders actions (urgent -> good practice).
4. For rules that are *almost* satisfied the engine asks a **follow-up question** (yes / no).
5. The **language interface** maps text to observations: `"tube well water is brown, pH 5.2, arsenic 25 ppb"`
   -> `src_borehole, col_brown, ph_low, arsenic_found`. `"no smell"` / `"not brown"` are understood as negations.

## Project structure
```
app.py                Streamlit UI (chat, checklist, report, knowledge-base browser)
engine.py             forward-chaining inference engine + explanations
nlp.py                natural-language understanding
rules.py              the 100 rules
assertions.py         the 300 assertions (+ keywords)
report.py             report formatting
tests/test_system.py  automated tests (python tests/test_system.py)
tools/export_kb.py    regenerates docs/KNOWLEDGE_BASE.md
docs/KNOWLEDGE_BASE.md  full list of rules and assertions
requirements.txt      dependencies
.streamlit/config.toml theme
```

## Run locally
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
python tests/test_system.py     # optional: run the tests
```

## Deploy live (GitHub -> Streamlit Community Cloud)
1. Create a new **public** repository on GitHub and upload **all files in this folder** (keep `app.py` at the
   repository root). Or from a terminal:
   ```bash
   git init && git add . && git commit -m "Water quality expert system"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
2. Go to <https://share.streamlit.io>, sign in with GitHub and click **Create app**.
3. Choose your repository, branch `main`, main file path `app.py`, then **Deploy**.
4. After a minute your app is live at `https://<app-name>.streamlit.app` - add that link to your submission.

## Demo inputs
- *"My tube well water is brown, smells like rotten eggs and tastes metallic. TDS 1400, arsenic 25 ppb. We have a baby and mix formula with it."*
- *"City supply water is cloudy after heavy rain, the whole family has diarrhea and vomiting. Chlorine 0."*
- *"Tested recently, pH 7.4, TDS 250, chlorine 0.5, no smell."*

## Thresholds used (WHO guideline values)
pH 6.5-8.5 · TDS > 1000 mg/L high · chlorine residual 0.2-5 mg/L · nitrate 50 mg/L · nitrite 3 mg/L ·
lead 10 ug/L · arsenic 10 ug/L · fluoride 1.5 mg/L · iron 0.3 mg/L · manganese 0.1 mg/L ·
copper 2 mg/L · turbidity 5 NTU · sulfate and chloride 250 mg/L · hardness: soft < 60, hard 121-180, very hard > 180 mg/L.

## Limitations
Keyword-based language understanding (no machine learning), simplified thresholds, no live data.
It is an educational prototype: confirm results with an accredited laboratory and consult a doctor for symptoms.
