"""Natural-language interface: turns free text into observation assertions.

Techniques: normalisation (UK/US spellings), keyword / phrase matching with word
boundaries, negation detection ("no smell", "not brown"), numeric lab-value
parsing ("pH 5.2", "arsenic 25 ppb") and simple intent detection (yes / no /
reset / help / why).
"""
import re
from assertions import OBSERVATIONS, OBS_BY_ID

SPELLING = {"colour": "color", "coloured": "colored", "odour": "odor", "odourless": "odorless",
            "faeces": "feces", "diarrhoea": "diarrhea", "sulphur": "sulfur", "sulphate": "sulfate",
            "mould": "mold", "mouldy": "moldy", "neighbour": "neighbor", "neighbours": "neighbors",
            "oesophagus": "esophagus", "e coli": "e. coli", "ph level": "ph"}
NEGATIONS = {"no", "not", "without", "never", "isn't", "isnt", "don't", "dont", "doesn't", "doesnt",
             "hasn't", "hasnt", "haven't", "havent", "didn't", "didnt", "nor", "none", "neither", "cannot", "can't"}
YES = {"yes", "yeah", "yep", "yup", "sure", "correct", "true", "right", "y", "ok", "okay", "haan", "ji"}
NO = {"no", "nope", "nah", "not really", "false", "n", "nahi", "incorrect"}


def normalize(text):
    t = text.lower().replace("\u2019", "'").replace("\u00b5", "u")
    for a, b in SPELLING.items():
        t = re.sub(r"\b" + re.escape(a) + r"\b", b, t)
    return re.sub(r"\s+", " ", t).strip()


# compile keyword patterns once: (obs_id, keyword, regex)
PATTERNS = []
for oid, _cat, _lab, kws in OBSERVATIONS:
    for kw in kws:
        k = normalize(kw)
        PATTERNS.append((oid, k, re.compile(r"(?<![a-z])" + re.escape(k) + r"(?:s|es)?(?![a-z])")))
PATTERNS.sort(key=lambda p: -len(p[1]))      # longest phrases first


def _negated(text, start, kw):
    """True if a negation word sits just before the keyword (same clause)."""
    first = kw.split()[0]
    if first in NEGATIONS or kw.startswith(("doesn't", "does not")):
        return False                          # the keyword itself is a negative phrase
    before = re.split(r"[.,;!?]| but | and | however ", text[:start])[-1]
    words = before.split()[-3:]
    return any(w in NEGATIONS for w in words)


# ---- numeric lab values --------------------------------------------------
UNIT = r"(?:\s*(ug/l|ppb|mg/l|ppm|ntu|mg/litre|mg per liter))?"
PARAMS = {
    "ph": ["ph"], "tds": ["tds", "total dissolved solids"],
    "chlorine": ["chlorine", "free chlorine", "residual chlorine"], "hardness": ["hardness", "total hardness"],
    "nitrate": ["nitrate", "nitrates"], "nitrite": ["nitrite"], "lead": ["lead"], "arsenic": ["arsenic"],
    "iron": ["iron"], "manganese": ["manganese"], "fluoride": ["fluoride"], "turbidity": ["turbidity"],
    "copper": ["copper"], "sulfate": ["sulfate"], "chloride": ["chloride"], "ammonia": ["ammonia"],
}
NUM_RE = {p: re.compile(r"(?<![a-z])(?:" + "|".join(map(re.escape, names)) + r")(?![a-z])"
                        r"(?:\s*(?:level|levels|reading|value|content|is|was|of|at|are|=|:|around|about|measured|came out|to be))*"
                        r"\s*[:=]?\s*(\d+(?:\.\d+)?)" + UNIT) for p, names in PARAMS.items()}


def _classify(param, v, unit):
    if param in ("lead", "arsenic") and unit in ("mg/l", "ppm", "mg/litre", "mg per liter"):
        v *= 1000                                           # convert mg/L -> ug/L
    out = []
    if param == "ph":
        out = ["ph_low"] if v < 6.5 else ["ph_ok"] if v <= 8.5 else ["ph_high"]
    elif param == "tds":
        out = ["tds_low"] if v < 50 else ["tds_ok"] if v <= 1000 else ["tds_high"] + (["tds_vhigh"] if v > 2000 else [])
    elif param == "chlorine":
        out = ["cl_none"] if v < 0.05 else ["cl_low"] if v < 0.2 else ["cl_ok"] if v <= 5 else ["cl_high"]
    elif param == "hardness":
        out = ["hard_soft"] if v < 60 else ["hard_hard"] if 120 < v <= 180 else ["hard_vhard"] if v > 180 else []
    elif param == "fluoride":
        out = ["fluoride_high"] if v > 1.5 else ["fluoride_low"] if v < 0.5 else []
    else:
        limit = {"nitrate": ("nitrate_high", 50), "nitrite": ("nitrite_high", 3), "lead": ("lead_found", 10),
                 "arsenic": ("arsenic_found", 10), "iron": ("iron_high", 0.3), "manganese": ("mn_high", 0.1),
                 "turbidity": ("turb_high", 5), "copper": ("copper_high", 2), "sulfate": ("sulfate_high", 250),
                 "chloride": ("chloride_high", 250), "ammonia": ("ammonia", 0.5)}[param]
        out = [limit[0]] if v > limit[1] else []
    return out


def parse(text):
    """Return dict(found=set, ruled_out=set, numbers=list of (param, value))."""
    t = normalize(text)
    found, ruled_out, numbers, taken = set(), set(), [], []
    for p, rx in NUM_RE.items():
        for m in rx.finditer(t):
            v = float(m.group(1))
            numbers.append((p, v))
            found.update(_classify(p, v, m.group(2)))
            taken.append(m.span())
    for oid, kw, rx in PATTERNS:
        for m in rx.finditer(t):
            if any(s <= m.start() < e for s, e in taken):
                continue
            (ruled_out if _negated(t, m.start(), kw) else found).add(oid)
            taken.append(m.span())
    ruled_out -= found
    return {"found": found, "ruled_out": ruled_out, "numbers": numbers}


def intent(text):
    """Detect simple commands and yes / no answers."""
    t = normalize(text).strip(" .!?")
    if re.search(r"\b(reset|start over|clear all|new case|restart)\b", t):
        return "reset"
    if re.fullmatch(r"(help|what can you do|how does this work|\?)", t) or t.startswith("help"):
        return "help"
    if re.match(r"(why|explain|how did you|reasoning|show rules|show trace)", t):
        return "why"
    if t in YES or re.fullmatch(r"(yes|yeah|yep)\b.*", t):
        return "yes"
    if t in NO or re.fullmatch(r"(no|nope|nah)\b[^a-z]*", t) or t == "not really":
        return "no"
    if re.fullmatch(r"(hi|hello|hey|salam|assalam o alaikum|as-salamu alaykum)\b.*", t) and len(t.split()) <= 4:
        return "greet"
    if re.fullmatch(r"(thanks|thank you|shukriya|ok thanks)\b.*", t):
        return "thanks"
    return None
