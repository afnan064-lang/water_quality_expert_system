"""Forward-chaining inference engine for the Drinking Water Quality Advisor."""
from assertions import OBS_BY_ID, DERIVED_BY_ID
from rules import RULES

RISK_RANK = {"r_unknown": 1, "r_low": 1, "r_moderate": 2, "r_high": 3, "r_critical": 4}
RISK_LABEL = {1: "LOW / UNKNOWN", 2: "MODERATE", 3: "HIGH", 4: "CRITICAL"}


def label(fid):
    """Human readable text of any assertion id."""
    if fid in OBS_BY_ID:
        return OBS_BY_ID[fid][2]
    return DERIVED_BY_ID[fid][2]


def kind(fid):
    return "observation" if fid in OBS_BY_ID else DERIVED_BY_ID[fid][1]


def _matches(rule, facts):
    if not all(c in facts for c in rule["all"]):
        return False
    for group in (rule["any"], rule["any2"]):
        if group and not any(c in facts for c in group):
            return False
    if any(n in facts for n in rule["no"]):
        return False
    if rule["none_kind"]:
        if any(kind(f) in rule["none_kind"] for f in facts if f not in OBS_BY_ID):
            return False
    return True


def infer(observations, rejected=()):
    """Run forward chaining over the given observation ids.

    Returns a dict with: facts, trace (list of fired rules), risk (1-4 + label),
    findings, causes, actions (sorted by priority) and follow-up questions.
    """
    obs = {o for o in observations if o in OBS_BY_ID}
    facts = set(obs)
    fired, trace, support = set(), [], {}

    for stage in (1, 2):
        stage_rules = [r for r in RULES if r["stage"] == stage]
        changed = True
        while changed:
            changed = False
            for rule in stage_rules:
                if rule["id"] in fired or not obs or not _matches(rule, facts):
                    continue
                fired.add(rule["id"])
                new = [f for f in rule["then"] if f not in facts]
                facts.update(rule["then"])
                for f in rule["then"]:
                    support.setdefault(f, []).append(rule["id"])
                trace.append({"rule": rule, "new": new})
                changed = True

    derived = [f for f in facts if f not in OBS_BY_ID]
    ranks = [RISK_RANK[f] for f in derived if f in RISK_RANK]
    level = max(ranks) if ranks else 0
    unknown_only = "r_unknown" in facts and level <= 1
    first_seen, severity = {}, {}
    for i, t in enumerate(trace):
        sev = max([RISK_RANK.get(x, 0) for x in t["rule"]["then"]] + [0])
        for f in t["rule"]["then"]:
            first_seen.setdefault(f, i)
            severity[f] = max(severity.get(f, 0), sev)

    def ordered(k):
        items = [f for f in derived if DERIVED_BY_ID[f][1] == k]
        return sorted(items, key=lambda f: (DERIVED_BY_ID[f][3], -severity.get(f, 0), first_seen.get(f, 0), f))

    actions = ordered("action")
    # keep a "no action" message only when nothing else is advised
    if len(actions) > 3 and "a_no_action" in actions:
        actions.remove("a_no_action")
    return {
        "facts": facts, "observations": obs, "trace": trace, "support": support,
        "risk_level": level, "risk_label": "UNKNOWN - TESTING NEEDED" if unknown_only else RISK_LABEL.get(level, "NOT ENOUGH INFORMATION"),
        "vulnerable": "r_vulnerable" in facts,
        "unverified": "h_unverified" in facts,
        "findings": ordered("hazard"), "causes": ordered("cause"), "actions": actions,
        "followups": follow_up_questions(facts, fired, set(rejected)),
    }


def follow_up_questions(facts, fired, rejected, limit=3):
    """Suggest observations that would complete rules which are almost satisfied."""
    scored = {}

    def suggest(fid, weight):
        if fid in OBS_BY_ID and fid not in facts and fid not in rejected:
            scored[fid] = max(scored.get(fid, 0), weight)

    for rule in RULES:
        if rule["id"] in fired or rule["stage"] != 1 or not rule["all"]:
            continue
        if any(n in facts for n in rule["no"]) or not any(c in facts for c in rule["all"]):
            continue
        weight = max([RISK_RANK.get(t, 0) for t in rule["then"]] + [0])
        missing = [c for c in rule["all"] if c not in facts]
        groups = [g for g in (rule["any"], rule["any2"]) if g and not any(c in facts for c in g)]
        if len(missing) == 1 and not groups:
            suggest(missing[0], weight)
        elif not missing and len(groups) == 1:
            for c in groups[0][:2]:
                suggest(c, weight)
    return sorted(scored, key=lambda f: -scored[f])[:limit]


def explain(result, fid):
    """Return the rules that concluded an assertion (for the 'why' feature)."""
    return result["support"].get(fid, [])


def rule_text(rule):
    """Readable IF ... THEN ... text for a rule."""
    parts = []
    if rule["all"]:
        parts.append(" AND ".join(label(c) for c in rule["all"]))
    for g in (rule["any"], rule["any2"]):
        if g:
            parts.append("(" + " OR ".join(label(c) for c in g) + ")")
    if rule["no"]:
        parts.append("NOT (" + " OR ".join(label(c) for c in rule["no"]) + ")")
    if rule["none_kind"]:
        parts.append("no hazards have been found")
    return "IF " + " AND ".join(parts) + " THEN " + "; ".join(label(t) for t in rule["then"])
