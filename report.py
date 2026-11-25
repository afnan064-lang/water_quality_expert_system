"""Formats inference results as readable text (used by the app and the tests)."""
from assertions import OBS_BY_ID, DERIVED_BY_ID
from engine import label

ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW / UNKNOWN": "🟢"}
DISCLAIMER = ("This is an educational expert-system prototype. Guideline values follow the WHO Guidelines "
              "for Drinking-water Quality; local standards may differ. It does not replace laboratory testing "
              "or advice from a doctor or water-quality professional.")


def risk_banner(result):
    if not result["observations"]:
        return "⚪ **Risk level: not enough information yet**"
    lab = result["risk_label"]
    icon = "⚪" if lab.startswith("UNKNOWN") else ICON.get(lab, "⚪")
    return f"{icon} **Overall risk: {lab}**"


def _group_actions(result):
    groups = {1: [], 2: [], 3: []}
    for a in result["actions"]:
        groups[DERIVED_BY_ID[a][3]].append(a)
    return groups


def brief(result, max_findings=5, max_actions=6):
    """Short summary used inside the chat."""
    lines = [risk_banner(result)]
    if result["vulnerable"]:
        lines.append("⚠️ *Vulnerable people (infants, pregnancy, elderly or weak immunity) are affected - take extra care.*")
    if result["findings"]:
        lines.append("\n**What I found**")
        lines += [f"- {label(f)}" for f in result["findings"][:max_findings]]
        extra = len(result["findings"]) - max_findings
        if extra > 0:
            lines.append(f"- *...and {extra} more (see the Full Report tab)*")
    if result["actions"]:
        lines.append("\n**What to do first**")
        lines += [f"{i}. {label(a)}" for i, a in enumerate(result["actions"][:max_actions], 1)]
    return "\n".join(lines)


def full_report(result):
    """Complete markdown report."""
    out = ["# Drinking Water Quality Report", "", risk_banner(result), ""]
    if result["vulnerable"]:
        out += ["> ⚠️ Vulnerable people are exposed: infants, pregnant women, the elderly or people with weak immunity.", ""]
    out.append("## Facts used")
    obs = sorted(result["observations"], key=lambda f: (OBS_BY_ID[f][1], f))
    out += [f"- *{OBS_BY_ID[f][1]}:* {label(f)}" for f in obs] or ["- none"]
    out += ["", "## Findings"] + ([f"- {label(f)}" for f in result["findings"]] or ["- none"])
    out += ["", "## Likely causes"] + ([f"- {label(f)}" for f in result["causes"]] or ["- none identified"])
    groups = _group_actions(result)
    for pr, title in ((1, "Do now (urgent)"), (2, "Do soon"), (3, "Good practice and notes")):
        if groups[pr]:
            out += ["", f"## {title}"] + [f"- {label(a)}" for a in groups[pr]]
    out += ["", "## Reasoning trace (rules fired)"]
    out += [f"- **{t['rule']['id']}** {t['rule']['name']}" for t in result["trace"]] or ["- none"]
    out += ["", f"*{DISCLAIMER}*"]
    return "\n".join(out)
