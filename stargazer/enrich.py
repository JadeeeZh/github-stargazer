"""Enrich each stargazer from their public GitHub profile HTML.

Free, no token. Extracts name, company, location, bio, personal website,
followers, top languages, notable repos, and any publicly listed
LinkedIn / Twitter / email. Resumable: one JSON per user under work/enriched/.
"""
import glob, json, os, re, time
from collections import Counter
from . import config, seed
from .http import get


def _find(h, *pats):
    for p in pats:
        m = re.search(p, h, re.S | re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def _clean_li(url):
    url = url.split("?")[0].rstrip("/")
    m = re.search(r"(https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company|pub)/[^/\s\"'>]+)", url, re.I)
    return m.group(1) if m else ""


def enrich_one(login):
    rec = {
        "login": login, "github_url": f"https://github.com/{login}",
        "github_name": "", "company": "", "location": "", "bio": "",
        "website": "", "followers": "", "linkedin_url": "", "twitter": "",
        "email": "", "top_languages": [], "notable_repos": [],
        "profile_status": "", "notes": "",
    }
    h, code = get(f"https://github.com/{login}")
    if code == 404:
        rec["profile_status"] = "404"
        rec["notes"] = "GitHub profile not found (renamed/deleted)."
        return rec
    if code != 200 or not h:
        rec["profile_status"] = f"http_{code}"
        rec["notes"] = f"fetch failed (HTTP {code})"
        return rec

    rec["github_name"] = _find(h, r'class="p-name[^"]*"[^>]*>\s*([^<]+?)\s*<')
    rec["bio"] = _find(h, r'data-bio-text="([^"]*)"',
                       r'class="p-note[^"]*"[^>]*>\s*<div[^>]*>\s*([^<]+?)\s*<')
    rec["company"] = _find(h,
                           r'itemprop="worksFor"[^>]*>.*?class="p-org"[^>]*>\s*(?:<div[^>]*>\s*)?([^<]+?)\s*<',
                           r'itemprop="worksFor".*?<span[^>]*>\s*([^<]+?)\s*</span>')
    rec["location"] = _find(h,
                            r'itemprop="homeLocation"[^>]*>.*?class="p-label"[^>]*>\s*([^<]+?)\s*<',
                            r'itemprop="homeLocation".*?<span[^>]*>\s*([^<]+?)\s*</span>')
    rec["followers"] = _find(h, r'tab=followers"[^>]*>\s*<span[^>]*>\s*([\d,\.km]+)\s*</span>')

    me_links = re.findall(r'rel="nofollow me"[^>]*href="(https?://[^"]+)"', h) + \
        re.findall(r'href="(https?://[^"]+)"[^>]*rel="nofollow me"', h) + \
        re.findall(r'itemprop="url"[^>]*>\s*<a[^>]*href="(https?://[^"]+)"', h)

    li = [u for u in me_links if "linkedin.com" in u.lower()]
    li += re.findall(r'https?://[a-z0-9.]*linkedin\.com/[^"\s<\\)]+', h, re.I)
    for c in li:
        cl = _clean_li(c)
        if cl:
            rec["linkedin_url"] = cl
            break

    tw = [u for u in me_links if re.search(r"(twitter|x)\.com", u, re.I)]
    tw += re.findall(r'https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+', h)
    tw = [u for u in tw if not re.search(r"/(intent|share|home|search|i/)", u, re.I)]
    if tw:
        rec["twitter"] = tw[0].split("?")[0].rstrip("/")

    for u in me_links:
        if not re.search(r"(linkedin\.com|twitter\.com|x\.com|github\.com)", u, re.I):
            rec["website"] = u.split("?")[0].rstrip("/")
            break

    em = _find(h, r'class="u-email"[^>]*>\s*([^<]+?@[^<]+?)\s*<', r'href="mailto:([^"]+)"')
    if em and "@" in em:
        rec["email"] = em.strip()

    rec["top_languages"] = [l for l, _ in Counter(
        re.findall(r'itemprop="programmingLanguage">([^<]+)<', h)).most_common(6)]
    rec["notable_repos"] = [re.sub(r"\s+", " ", x).strip()
                            for x in re.findall(r'class="repo"[^>]*>([^<]+)<', h)][:6]

    rich = any([rec["github_name"].strip() not in ("", login), rec["bio"], rec["company"],
                rec["location"], rec["website"], rec["linkedin_url"], rec["top_languages"]])
    rec["profile_status"] = "ok" if rich else "sparse"
    return rec


def rebuild_combined(slug, out_path=None):
    """Rebuild this repo's union snapshot (stars ∪ forks) from the SHARED profile cache.

    Network-free. Re-stamps `best_rank` from the seed files so the cache's untrusted
    `rank` field is never relied on for sort/recency. Writes .cache/repos/<key>/union.json.
    """
    out_path = out_path or config.repo_paths(slug)["union"]
    seeds = seed.load_seeds(slug)
    combined = []
    for lo in seed.all_logins(slug, seeds):
        p = config.profile_path(lo)
        if not os.path.exists(p):
            continue
        rec = dict(json.load(open(p, encoding="utf-8")))  # don't mutate the cached object
        rec["best_rank"] = seed.source_of(lo, seeds)["best_rank"]
        combined.append(rec)
    combined.sort(key=lambda r: r.get("best_rank", 1e9))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    return combined


def _stamp_enriched(slug):
    """Update repo.json.last_enriched_at — the staleness writer (only enrich does this)."""
    import datetime
    rp = config.repo_paths(slug)
    meta = {}
    if os.path.exists(rp["repo_json"]):
        try:
            meta = json.load(open(rp["repo_json"], encoding="utf-8"))
        except Exception:
            meta = {}
    meta["repo"] = slug
    meta["repo_key"] = config.repo_key(slug)
    meta["last_enriched_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(rp["repo_json"], "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def run(slug, sleep=0.4, limit=0):
    """Enrich this repo's stargazers ∪ forkers into the SHARED profile cache (resumable).

    Only scrapes logins not already cached (cache is shared across repos). Returns
    (combined, scraped_count).
    """
    config.ensure_dirs()
    seeds = seed.load_seeds(slug)
    logins = seed.all_logins(slug, seeds)
    if limit:
        logins = logins[:limit]
    rank_of = {lo: seed.source_of(lo, seeds)["best_rank"] for lo in logins}
    done = {os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(config.PROFILES, "*.json"))}
    todo = [lo for lo in logins if lo not in done]
    print(f"{len(logins)} stars+forks | {len(done)} profiles cached | {len(todo)} to scrape")

    li = ok = sparse = miss = 0
    for i, lo in enumerate(todo):
        rec = enrich_one(lo)
        rec["rank"] = rank_of.get(lo, 10 ** 9)
        with open(config.profile_path(lo), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        li += bool(rec["linkedin_url"])
        ok += rec["profile_status"] == "ok"
        sparse += rec["profile_status"] == "sparse"
        miss += rec["profile_status"] not in ("ok", "sparse")
        if (i + 1) % 25 == 0:
            print(f"  ...{i+1}/{len(todo)} (ok={ok} sparse={sparse} miss={miss} linkedin={li})")
        time.sleep(sleep)

    combined = rebuild_combined(slug)
    _stamp_enriched(slug)
    print(f"\nDONE: {len(combined)} profiles in union ({slug}) | scraped {len(todo)} this run | "
          f"linkedin={sum(1 for r in combined if r['linkedin_url'])} "
          f"website={sum(1 for r in combined if r['website'])} "
          f"company={sum(1 for r in combined if r['company'])}")
    return combined, len(todo)
