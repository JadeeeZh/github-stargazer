"""Step 3: ICP filtering — split CRM leads into B-end (target companies) and
C-end (high-potential individuals), match against a tolerant ICP.md, and score.

The ICP file is markdown and arrives later; the parser NEVER raises — a missing,
empty, or garbage file yields a neutral matcher (ranking still works off source
weight + existing signals, so forkers still outrank stargazers).

Key safety properties (see icp.example.md for the schema):
- headings matched by keyword; a heading matching >=2 section classes is ignored;
- keywords matched on word boundaries (so 'ml' != 'html', 'ai' != 'paid');
- real-company detection is conservative (placeholder/location -> C), but a
  LinkedIn-verified company overrides the denylist.
"""
import re
from . import config, crm
from . import seed

# A heading is assigned to a section class only if it uniquely matches one class.
_SECTION_KEYS = {
    "b": ["b-end", "b端", "b2b", "target compan", "account", "目标客户", "公司"],
    "c": ["c-end", "c端", "individual", "persona", "indie", "个人", "高潜"],
    "seniority": ["seniority", "title", "role", "职级", "职位"],
    "exclude": ["exclusion", "exclude", "排除", "negative", "avoid"],
    "weight": ["weight", "权重"],
    "product": ["product", "产品"],
}
DEFAULT_WEIGHTS = {"icp": 3, "ai_focus": 3, "seniority": 2, "recency": 1, "identifiability": 1}


class ICP:
    def __init__(self):
        self.b_keywords = []
        self.b_exclude = []
        self.c_keywords = []
        self.c_exclude = []
        self.seniority = []
        self.exclude = []
        self.weights = dict(DEFAULT_WEIGHTS)
        self.warnings = []
        self.loaded = False
        self.path = ""


def _canon(heading):
    """Return the unique matching section class, or None if zero or ambiguous (>=2)."""
    h = heading.lower()
    hits = [c for c, keys in _SECTION_KEYS.items() if any(k in h for k in keys)]
    return hits[0] if len(hits) == 1 else None


def _terms(item):
    """Split a bullet into terms on commas / CJK commas only — keep '/' and '-' literal."""
    return [t.strip().lower() for t in re.split(r"[,，、]", item) if t.strip()]


def load(path=None):
    """NEVER raises. Missing/empty/garbage -> ICP(loaded=False) neutral matcher.
    path may be an explicit file; None -> the sole ICP in icps/ (else neutral)."""
    icp = ICP()
    try:
        if path is None:
            path, _ = config.resolve_icp(None)
        text = open(path, encoding="utf-8").read()
    except BaseException:
        return icp
    icp.path = path
    cur = None
    in_comment = False
    for raw in text.splitlines():
        s = raw.strip()
        if in_comment:
            if "-->" in s:
                in_comment = False
            continue
        if s.startswith("<!--"):
            if "-->" not in s:
                in_comment = True
            continue
        if not s:
            continue
        m = re.match(r"^#{1,6}\s+(.*)", s)
        if m:
            heading = m.group(1)
            cur = _canon(heading)
            if cur is None and any(any(k in heading.lower() for k in ks)
                                   for ks in _SECTION_KEYS.values()):
                icp.warnings.append(f"ambiguous/unknown heading ignored: {heading!r}")
            continue
        mw = re.match(r"(?i)^[-*]?\s*weight\s+([a-z_]+)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*$", s)
        if mw and cur == "weight":
            try:
                icp.weights[mw.group(1).lower()] = max(0.0, min(5.0, float(mw.group(2))))
            except ValueError:
                icp.warnings.append(f"bad weight: {s!r}")
            continue
        mb = re.match(r"^[-*]\s*(.*)", s)
        if not mb or cur is None:
            continue
        item = mb.group(1).strip()
        excl = item.startswith("!")
        if excl:
            item = item[1:].strip()
        item = re.sub(r"(?i)^keywords?\s*[:：]\s*", "", item)
        terms = _terms(item)
        if not terms:
            continue
        if cur == "b":
            (icp.b_exclude if excl else icp.b_keywords).extend(terms)
        elif cur == "c":
            (icp.c_exclude if excl else icp.c_keywords).extend(terms)
        elif cur == "seniority":
            icp.seniority.extend(terms)
        elif cur == "exclude":
            icp.exclude.extend(terms)
    icp.loaded = (any([icp.b_keywords, icp.c_keywords, icp.exclude, icp.seniority])
                  or icp.weights != DEFAULT_WEIGHTS)
    return icp


# ---------- real-company / placeholder detection ----------
_PLACEHOLDER_GENERIC = {
    "remote", "freelance", "freelancer", "independent", "self", "self-employed", "self employed",
    "selfemployed", "none", "n/a", "na", "-", "home", "earth", "world", "worldwide", "internet",
    "nomad", "open source", "oss", "student", "unemployed", "looking for work", "open to work",
    "personal", "myself", "me", "自由", "自由职业", "无", "独立开发者", "个人", "传统公司",
    "available", "available for hire", "available for work", "for hire", "hiring",
    "we are hiring", "looking", "seeking", "job seeker", "学生", "在校学生", "求职中",
}
_LOCATION_DENYLIST = {
    "remote", "worldwide", "earth", "beijing", "shanghai", "shenzhen", "hangzhou", "guangzhou",
    "chengdu", "hefei", "china", "usa", "us", "u.s.", "uk", "u.k.", "france", "germany", "spain",
    "italy", "india", "canada", "japan", "korea", "singapore", "viet nam", "vietnam", "europe",
    "asia", "africa", "california", "new york", "nyc", "san francisco", "sf", "bay area", "seattle",
    "boston", "austin", "london", "paris", "berlin", "munich", "bavaria", "amsterdam", "tokyo",
    "seoul", "toronto", "sydney", "bangalore", "bengaluru", "mumbai", "delhi", "taipei",
    "hong kong", "北京", "上海", "中国", "杭州", "深圳",
}


def _norm_company(s):
    return re.sub(r"[^\w一-鿿 /.&-]", "", (s or "").lower()).strip()


# Coarse company-TYPE triage for the B-end feed (a hint, not gospel).
_BIGTECH = {
    "microsoft", "google", "alphabet", "youtube", "tencent", "alibaba", "bytedance", "baidu",
    "amazon", "aws", "meta", "facebook", "apple", "nvidia", "huawei", "ibm", "oracle", "salesforce",
    "sap", "intel", "samsung", "tiktok", "jd", "meituan", "xiaomi", "didi", "netease", "uber",
    "stripe", "databricks", "snowflake", "adobe", "cisco", "netflix", "paypal", "shein", "grab",
    "panasonic", "sony", "lg", "tesla", "linkedin", "slack", "atlassian", "shopify", "twilio",
}
_ACAD_RE = re.compile(
    r"universit|\bcollege\b|institute of tech|polytechnic|\bschool\b|academy of|"
    r"大学|学院|中学|研究院|国家.*实验室|research (institute|center|centre)", re.I)


def company_category(name):
    """candidate | academic | bigtech | junk — type triage for B-end companies.
    Per the ICP, academic (not an agent company) and bigtech (builds own) are usually DQ;
    'candidate' is a real-ish company worth researching."""
    n = _norm_company(name)
    if not n or len(n) <= 2:
        return "junk"
    toks = n.split()
    if n in _BIGTECH or any(t in _BIGTECH for t in toks):
        return "bigtech"
    if _ACAD_RE.search(name or ""):
        return "academic"
    if n in _PLACEHOLDER_GENERIC or not any(ch.isalpha() for ch in n):
        return "junk"
    return "candidate"


def has_real_company(r):
    raw = (r.get("company") or "").strip()
    c = crm.disp_company(r).strip()
    if not c:
        return False
    # a VERIFIED LinkedIn company is trusted as real, overriding denylists,
    # unless it is an obvious generic placeholder.
    licomp = (r.get("linkedin_company") or "").strip()
    if licomp and r.get("linkedin_confidence") == "high" \
            and _norm_company(licomp) not in _PLACEHOLDER_GENERIC:
        return True
    cl = c.lower().strip()
    if cl.startswith("@"):
        cl = cl[1:].strip()
    if not any(ch.isalpha() for ch in cl):
        return False  # emoji / symbols only
    if _norm_company(cl) in _PLACEHOLDER_GENERIC:
        return False
    loc = (r.get("location") or "").strip().lower()
    toks = [t for t in re.split(r"[\s,/|]+", cl) if t]
    is_location = (len(toks) <= 3 and (cl == loc or _norm_company(raw).lower() == loc
                   or cl in _LOCATION_DENYLIST
                   or (toks and all(t in _LOCATION_DENYLIST for t in toks))))
    return not is_location


# ---------- ICP matcher + bucket ----------
_RE_CACHE = {}


def _kw_re(term):
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", re.I)


def _hit(term, text):
    rx = _RE_CACHE.get(term)
    if rx is None:
        rx = _RE_CACHE[term] = _kw_re(term)
    return bool(rx.search(text))


def _ai_fit(r):
    return crm.focus(r) in ("AI agents / LLM", "ML / Data science")


def _followers_int(r):
    s = (r.get("followers") or "").strip().lower().replace(",", "")
    m = re.match(r"(\d+(?:\.\d+)?)\s*([km]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) * {"k": 1e3, "m": 1e6, "": 1}[m.group(2)])


def match(r, icp):
    """-> {"b_hits", "c_hits", "excluded"}. Pure. Neutral (0,0) if icp not loaded.
    B hits scored from the company field; C/exclusion hits from the non-company blob."""
    base = (crm._blob(r) + " " + (r.get("location") or "")).lower()
    comp = crm.disp_company(r).lower()
    excluded = bool(icp.exclude) and any(_hit(x, base) or _hit(x, comp) for x in icp.exclude)
    if not icp.loaded:
        return {"b_hits": 0, "c_hits": 0, "excluded": excluded}
    b = sum(1 for k in icp.b_keywords if _hit(k, comp))
    if icp.b_exclude and any(_hit(x, comp) for x in icp.b_exclude):
        excluded = True
    c = sum(1 for k in icp.c_keywords if _hit(k, base))
    if icp.c_exclude and any(_hit(x, base) for x in icp.c_exclude):
        excluded = True
    return {"b_hits": b, "c_hits": c, "excluded": excluded}


def bucket(r, m):
    """Real company -> B. Else C only if a genuine individual signal exists. Else 'neither'."""
    if has_real_company(r):
        return "B"
    indiv_signal = (m["c_hits"] > 0 or _ai_fit(r) or _followers_int(r) >= 100
                    or bool(r.get("notable_repos")))
    return "C" if indiv_signal else "neither"


# ---------- scoring + grading ----------
W_SOURCE = 1.0
W_ICP = 1.0
GRADE_A_FLOOR = 9.0
GRADE_B_FLOOR = 5.0


def score(r, icp, src, bkt, m):
    """Pure; m is the precomputed match, src is seed.source_of(...)."""
    w = icp.weights
    src_pts = seed.SOURCE_WEIGHT[src["source"]] * W_SOURCE
    hits = 0 if bkt == "neither" else (m["b_hits"] if bkt == "B" else m["c_hits"])
    icp_pts = w["icp"] * hits * W_ICP
    sig = (w["ai_focus"] if _ai_fit(r) else 0)
    if crm.seniority(r) == "Leadership" or any(_hit(k, crm._blob(r).lower()) for k in icp.seniority):
        sig += w["seniority"]
    if r.get("linkedin_confidence") == "high":
        sig += w["identifiability"] * 2
    elif r.get("linkedin_url") or r.get("website") or has_real_company(r):
        sig += w["identifiability"]
    if src["best_rank"] <= 50:
        sig += w["recency"] * 2
    elif src["best_rank"] <= 200:
        sig += w["recency"]
    total = src_pts + icp_pts + sig
    if m["excluded"]:
        total = total / 4.0  # demote hard, never delete
    return round(total, 3)


def grade(s, excluded):
    if excluded:
        return "C"
    if s >= GRADE_A_FLOOR:
        return "A"
    if s >= GRADE_B_FLOOR:
        return "B"
    return "C"
