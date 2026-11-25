"""Drinking Water Quality Advisor - Expert System (Streamlit app)."""
import streamlit as st
import pandas as pd

import nlp
from assertions import OBSERVATIONS, DERIVED, OBS_BY_ID
from rules import RULES
from engine import infer, label, rule_text
from report import brief, full_report, risk_banner, DISCLAIMER

st.set_page_config(page_title="Drinking Water Quality Advisor", page_icon="💧", layout="wide")

EXAMPLES = {
    "Brown borehole water + baby": "My tube well water is brown, smells like rotten eggs and tastes metallic. "
                                   "TDS 1400, arsenic 25 ppb. We have a baby and mix formula with it.",
    "Family sick after rain": "City supply water is cloudy after heavy rain, the whole family has diarrhea and "
                              "vomiting. Chlorine 0.",
    "Good lab results": "Tested recently, pH 7.4, TDS 250, chlorine 0.5, no smell.",
}
WELCOME = ("Hello! I'm the **Drinking Water Quality Advisor**. Describe your water in your own words - colour, "
           "smell, taste, source, lab numbers (e.g. *pH 5.2, arsenic 25 ppb*), health symptoms or who drinks it. "
           "Type **help** for tips or **reset** to start a new case.")
HELP = ("**How to talk to me**\n- Describe symptoms: *\"water is brown and smells like rotten eggs\"*\n"
        "- Give sources: *\"we use a tube well / municipal supply / tanker\"*\n"
        "- Give lab numbers: *\"pH 5.2, TDS 1400, nitrate 70, lead 20 ug/L\"* (lead and arsenic default to ug/L)\n"
        "- Mention people: *\"we have a baby / pregnant woman\"*\n"
        "- Negations work: *\"no smell\"*, *\"not brown\"*\n"
        "- Answer my yes/no follow-up questions\n- **why** shows the rules I used - **reset** clears the case")

# ------------------------------------------------------------------ state
S = st.session_state
S.setdefault("facts", set())
S.setdefault("rejected", set())
S.setdefault("messages", [{"role": "assistant", "content": WELCOME}])
S.setdefault("pending", None)
S.setdefault("queued", None)


def reset_case():
    S.facts, S.rejected, S.pending = set(), set(), None
    S.messages = [{"role": "assistant", "content": WELCOME}]


def understood(found, ruled_out, numbers):
    lines = []
    if found:
        lines.append("**I understood:** " + "; ".join(label(f) for f in sorted(found)))
    if ruled_out:
        lines.append("**Ruled out:** " + "; ".join(label(f) for f in sorted(ruled_out)))
    if numbers:
        lines.append("*Numbers read:* " + ", ".join(f"{p} = {v:g}" for p, v in numbers))
    return "\n\n".join(lines)


def ask_next(result):
    S.pending = result["followups"][0] if result["followups"] else None
    return f"\n\n❓ **Quick check:** {label(S.pending)}? *(yes / no)*" if S.pending else ""


def reply_to(text):
    it = nlp.intent(text)
    if it == "reset":
        reset_case()
        return None
    if it == "help":
        return HELP
    if it in ("greet", "thanks"):
        return ("You're welcome! Tell me more about your water or type **reset** for a new case."
                if it == "thanks" else WELCOME)
    if it == "why":
        res = infer(S.facts, S.rejected)
        if not res["trace"]:
            return "I haven't fired any rules yet - describe your water first."
        return "**Rules I used:**\n\n" + "\n".join(f"- **{t['rule']['id']}** {t['rule']['name']}" for t in res["trace"])
    if it in ("yes", "no") and not S.pending:
        return "I haven't asked you a question right now - tell me more about your water instead."
    if it in ("yes", "no"):
        fid, S.pending = S.pending, None
        (S.facts.add if it == "yes" else S.rejected.add)(fid)
        res = infer(S.facts, S.rejected)
        return (f"Noted: **{label(fid)}** - {'yes' if it == 'yes' else 'no'}.\n\n" + brief(res) + ask_next(res))
    parsed = nlp.parse(text)
    if not parsed["found"] and not parsed["ruled_out"]:
        return ("I couldn't recognise any water-quality details in that. Try e.g. *\"my well water is cloudy and "
                "smells of sewage\"* or *\"pH 5.2 and arsenic 25 ppb\"*. Type **help** for more examples.")
    S.facts |= parsed["found"]
    S.facts -= parsed["ruled_out"]
    S.rejected = (S.rejected | parsed["ruled_out"]) - parsed["found"]
    res = infer(S.facts, S.rejected)
    return understood(parsed["found"], parsed["ruled_out"], parsed["numbers"]) + "\n\n" + brief(res) + ask_next(res)


# ------------------------------------------------------------------ input handling
prompt = st.chat_input("Describe your water (e.g. 'brown well water, rotten egg smell, pH 5.2')")
prompt = prompt or S.queued
S.queued = None
if prompt:
    S.messages.append({"role": "user", "content": prompt})
    answer = reply_to(prompt)
    if answer:
        S.messages.append({"role": "assistant", "content": answer})

result = infer(S.facts, S.rejected)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("💧 Water Advisor")
    st.caption("Rule-based expert system · forward chaining")
    c1, c2 = st.columns(2)
    c1.metric("Rules", len(RULES))
    c2.metric("Assertions", len(OBSERVATIONS) + len(DERIVED))
    st.markdown("#### Try an example")
    for name, text in EXAMPLES.items():
        if st.button(name):
            S.queued = text
            st.rerun()
    if st.button("🔄 Reset case"):
        reset_case()
        st.rerun()
    st.markdown("#### Facts in this case")
    if S.facts:
        for f in sorted(S.facts, key=lambda x: (OBS_BY_ID[x][1], x)):
            st.markdown(f"- {label(f)}")
    else:
        st.caption("Nothing yet.")
    st.caption(DISCLAIMER)

# ------------------------------------------------------------------ main tabs
tab_chat, tab_check, tab_report, tab_kb, tab_about = st.tabs(
    ["💬 Chat advisor", "☑️ Checklist", "📋 Full report", "📚 Knowledge base", "ℹ️ About"])

with tab_chat:
    st.subheader("Drinking Water Quality Advisor")
    for m in S.messages:
        with st.chat_message(m["role"], avatar="💧" if m["role"] == "assistant" else None):
            st.markdown(m["content"])

with tab_check:
    st.subheader("Prefer a checklist?")
    st.caption("Tick everything that applies, then add it to the case. You can mix this with the chat.")
    cats = []
    for o in OBSERVATIONS:
        if o[1] not in cats:
            cats.append(o[1])
    with st.form("checklist"):
        picked = set()
        cols = st.columns(2)
        for i, cat in enumerate(cats):
            ids = [o[0] for o in OBSERVATIONS if o[1] == cat]
            with cols[i % 2]:
                sel = st.multiselect(cat, ids, default=[x for x in ids if x in S.facts],
                                     format_func=lambda x: OBS_BY_ID[x][2], key=f"ck_{cat}")
                picked |= set(sel)
        if st.form_submit_button("Analyse selected facts", type="primary"):
            S.facts = picked
            S.pending = None
            st.rerun()

with tab_report:
    st.subheader("Full report")
    st.markdown(risk_banner(result))
    if result["observations"]:
        md = full_report(result)
        st.markdown(md)
        st.download_button("⬇️ Download report (.md)", md, file_name="water_quality_report.md")
        with st.expander("🔍 Reasoning trace: how each conclusion was reached"):
            for t in result["trace"]:
                st.markdown(f"**{t['rule']['id']} - {t['rule']['name']}**")
                st.caption(rule_text(t["rule"]))
    else:
        st.info("No facts yet - describe your water in the chat or use the checklist.")

with tab_kb:
    st.subheader("Knowledge base")
    st.markdown(f"**{len(RULES)} rules** · **{len(OBSERVATIONS) + len(DERIVED)} assertions** "
                f"({len(OBSERVATIONS)} observations you can report + {len(DERIVED)} derived findings, risks, causes and actions)")
    q = st.text_input("Filter rules / assertions", placeholder="e.g. arsenic, R42, boil")
    rules_df = pd.DataFrame([{"ID": r["id"], "Rule": r["name"], "IF ... THEN": rule_text(r)} for r in RULES])
    kinds = {"observation": "Observation"}
    ass_df = pd.DataFrame(
        [{"ID": o[0], "Type": "Observation", "Group": o[1], "Meaning": o[2]} for o in OBSERVATIONS] +
        [{"ID": d[0], "Type": d[1].capitalize(), "Group": "", "Meaning": d[2]} for d in DERIVED])
    if q:
        rules_df = rules_df[rules_df.apply(lambda r: q.lower() in " ".join(map(str, r)).lower(), axis=1)]
        ass_df = ass_df[ass_df.apply(lambda r: q.lower() in " ".join(map(str, r)).lower(), axis=1)]
    t1, t2 = st.tabs([f"Rules ({len(rules_df)})", f"Assertions ({len(ass_df)})"])
    t1.dataframe(rules_df, hide_index=True)
    t2.dataframe(ass_df, hide_index=True)

with tab_about:
    st.subheader("About this expert system")
    st.markdown("""
**Domain:** household drinking-water quality - diagnosing problems from appearance, taste, smell, source,
plumbing, lab results and health symptoms, then advising what to do.

**Architecture**
1. **Knowledge base** - 100 IF-THEN rules (`rules.py`) over 300 assertions (`assertions.py`).
2. **Inference engine** - forward chaining to a fixed point in two stages, with a reasoning trace and
   follow-up questions for almost-satisfied rules (`engine.py`).
3. **Natural-language interface** - keyword/phrase matching, negation, numeric lab-value parsing and
   yes/no dialogue (`nlp.py`) inside a Streamlit chat UI (`app.py`).

**Limits:** keyword-based language understanding, WHO-based thresholds, no live data. Always confirm
with an accredited laboratory.
""")
