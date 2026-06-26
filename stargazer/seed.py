"""Join the star + fork seed files into per-login source provenance.

Source and rank live ONLY here and in the seed JSON files — never in the
per-user enrich cache (work/enriched/<login>.json). The cache's `rank` field is
UNTRUSTED for the GTM pipeline: fork-only cached files hold fork ranks that
collide numerically with star ranks, so GTM always re-stamps `best_rank` from
these seeds at build time.
"""
import json
from . import config

SOURCE_WEIGHT = {"both": 3, "fork": 2, "star": 1}   # fork > star; both strongest
SOURCE_ORDER = {"both": 0, "fork": 1, "star": 2}     # tie-break / display precedence


def _safe_load(path, list_key):
    try:
        return json.load(open(path, encoding="utf-8")).get(list_key, [])
    except Exception:
        return []


def load_seeds(slug):
    """-> {login: {"star_rank", "fork_rank", "forked_at"}} for one repo. Missing file = empty.

    Keeps the lowest (newest) rank on duplicates. Trusts len(list), not the
    possibly-stale `count` field in the seed JSON.
    """
    paths = config.repo_paths(slug)
    blank = {"star_rank": None, "fork_rank": None, "forked_at": None, "starred_at": None}
    seeds = {}
    for m in _safe_load(paths["stargazers"], "stargazers"):
        lo = m.get("login")
        if not lo:
            continue
        e = seeds.setdefault(lo, dict(blank))
        r = m.get("rank")
        if isinstance(r, int) and (e["star_rank"] is None or r < e["star_rank"]):
            e["star_rank"] = r
        e["starred_at"] = m.get("starred_at") or e["starred_at"]  # only if API fetch captured it
    for m in _safe_load(paths["forkers"], "forkers"):
        lo = m.get("login")
        if not lo:
            continue
        e = seeds.setdefault(lo, dict(blank))
        r = m.get("rank")
        if isinstance(r, int) and (e["fork_rank"] is None or r < e["fork_rank"]):
            e["fork_rank"] = r
            e["forked_at"] = m.get("forked_at") or e["forked_at"]
    return seeds


def all_logins(slug, seeds=None):
    """Union for one repo: stars in star-rank order, then NEW forkers in fork-rank order."""
    seeds = seeds if seeds is not None else load_seeds(slug)
    stars = sorted([l for l, v in seeds.items() if v["star_rank"] is not None],
                   key=lambda l: seeds[l]["star_rank"])
    star_set = set(stars)
    forks = sorted([l for l, v in seeds.items()
                    if v["fork_rank"] is not None and l not in star_set],
                   key=lambda l: seeds[l]["fork_rank"])
    return stars + forks


def source_of(login, seeds):
    """-> {source, star_rank, fork_rank, best_rank, best_clock, forked_at, starred_at, engaged_at}.

    engaged_at = the real date (YYYY-MM-DD) they engaged — fork date preferred, else star date.
    star dates are only present when stargazers were fetched via the API (token); HTML fetch
    has none, so engaged_at is "" for star-only HTML-sourced leads.
    """
    v = seeds.get(login, {"star_rank": None, "fork_rank": None, "forked_at": None, "starred_at": None})
    sr, fr = v["star_rank"], v["fork_rank"]
    src = "both" if (sr is not None and fr is not None) else "fork" if fr is not None else "star"
    cands = [(r, clk) for r, clk in ((sr, "star"), (fr, "fork")) if isinstance(r, int)]
    best_rank, best_clock = (min(cands) if cands else (10 ** 9, "none"))
    forked_at, starred_at = v.get("forked_at"), v.get("starred_at")
    engaged_at = ((forked_at or starred_at or "")[:10])  # date part; fork date preferred
    return {"source": src, "star_rank": sr, "fork_rank": fr, "best_rank": best_rank,
            "best_clock": best_clock, "forked_at": forked_at, "starred_at": starred_at,
            "engaged_at": engaged_at}
