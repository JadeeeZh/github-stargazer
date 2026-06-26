"""Name validation for looked-up LinkedIn URLs — guards against false positives.

Ported from the deepline linkedin-url-lookup recipe's validation rules:
- last name: exact or substring match
- first name: exact, 3+ char prefix, or known nickname
- accents normalized, punctuation/emoji stripped before comparing
"""
import re, unicodedata

NICKNAMES = {
    "mike": "michael", "bob": "robert", "bill": "william", "liz": "elizabeth",
    "beth": "elizabeth", "alex": "alexander", "dan": "daniel", "danny": "daniel",
    "sara": "sarah", "tom": "thomas", "tony": "anthony", "chris": "christopher",
    "jim": "james", "jimmy": "james", "joe": "joseph", "rob": "robert",
    "nick": "nicholas", "rick": "richard", "dick": "richard", "ed": "edward",
    "ted": "edward", "andy": "andrew", "ben": "benjamin", "sam": "samuel",
    "kate": "katherine", "katie": "katherine", "matt": "matthew", "greg": "gregory",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z\s'-]", " ", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def split_name(full):
    toks = [t for t in norm(full).replace("-", " ").split() if len(t) > 1]
    if not toks:
        return "", ""
    return toks[0], toks[-1]


def _first_match(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 3 and (b.startswith(a) or a.startswith(b)):
        return True
    return NICKNAMES.get(a) == b or NICKNAMES.get(b) == a or \
        NICKNAMES.get(a) == NICKNAMES.get(b) and NICKNAMES.get(a) is not None


def names_match(source_name, candidate_name):
    """True if candidate_name plausibly refers to the same person as source_name."""
    sf, sl = split_name(source_name)
    cf, cl = split_name(candidate_name)
    if not (sf and sl and cf and cl):
        return False
    last_ok = sl == cl or sl in cl or cl in sl
    return last_ok and _first_match(sf, cf)


def looks_like_person(name):
    """Heuristic: a real human first+last, not a handle/org/placeholder."""
    n = norm(name)
    toks = n.split()
    if len(toks) < 2:
        return False
    if any(len(t) < 2 for t in toks[:2]):
        return False
    blob = name.lower()
    bad = ["inc", "llc", "ltd", "corp", "studio", "labs", "official", "team",
           "bot", "ai ", "technologies", "solutions", "group", "ventures"]
    if any(b in blob for b in bad):
        return False
    return True
