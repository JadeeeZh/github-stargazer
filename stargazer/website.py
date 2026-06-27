"""Free LinkedIn/contact discovery over personal websites.

For each enriched stargazer with a website but no LinkedIn, fetch the site (and a
few likely sub-pages) and harvest LinkedIn / Twitter / email. Updates the per-user
JSON in place, then rebuilds the combined enriched.json.
"""
import glob, json, os, re, time
from . import config, seed
from .http import get
from .enrich import rebuild_combined

SUBPAGES = ["", "/about", "/contact"]  # trimmed for speed (was 6 pages)


def _clean_li(url):
    url = url.split("?")[0].rstrip("/")
    m = re.search(r"(https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company|pub)/[^/\s\"'>]+)", url, re.I)
    return m.group(1) if m else ""


def _crawl(base):
    base = base.rstrip("/")
    li = tw = em = ""
    for sp in SUBPAGES:
        html, status = get(base + sp, timeout=8, tries=1, max_bytes=400_000)
        if status != 200 or not html:
            continue
        if not li:
            for c in re.findall(r'https?://[a-z0-9.]*linkedin\.com/[^"\s<\\)\']+', html, re.I):
                cl = _clean_li(c)
                if cl:
                    li = cl
                    break
        if not tw:
            for c in re.findall(r'https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+', html):
                if not re.search(r"/(intent|share|home|search|i/)", c, re.I):
                    tw = c.split("?")[0].rstrip("/")
                    break
        if not em:
            m = re.search(r'mailto:([^"\'>\s]+@[^"\'>\s]+)', html)
            if m:
                em = m.group(1)
        if li:
            break
    return li, tw, em


def run(slugs=None, sleep=0.5, recheck=False):
    """Crawl personal sites in the SHARED profile cache for LinkedIn/contact, then rebuild
    union.json for the affected repos. slugs=None -> all cached repos.

    Idempotent: each site is crawled at most once (a `website_checked` marker is set whether
    or not anything was found), and when slugs are given only those repos' people are considered
    — so a `run` on a new repo doesn't re-crawl the whole shared cache. Pass recheck=True to redo.
    """
    allowed = None
    if slugs:
        allowed = set()
        for s in slugs:
            allowed |= set(seed.all_logins(s))
    targets = []
    for fp in sorted(glob.glob(os.path.join(config.PROFILES, "*.json"))):
        r = json.load(open(fp, encoding="utf-8"))
        if not (r.get("website") and not r.get("linkedin_url")):
            continue
        if not recheck and r.get("website_checked"):
            continue
        if allowed is not None and r.get("login") not in allowed:
            continue
        targets.append((fp, r))
    print(f"{len(targets)} profiles with an unchecked website -> crawling")

    fli = ftw = fem = 0
    for i, (fp, r) in enumerate(targets):
        li, tw, em = _crawl(r["website"])
        if li and not r.get("linkedin_url"):
            r["linkedin_url"] = li; fli += 1
        if tw and not r.get("twitter"):
            r["twitter"] = tw; ftw += 1
        if em and not r.get("email"):
            r["email"] = em; fem += 1
        if li or tw or em:
            r["notes"] = ((r.get("notes", "") or "") + " | enriched from personal website").strip(" |")
        r["website_checked"] = True  # mark whether or not anything was found -> never re-crawl
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        if (i + 1) % 10 == 0:
            print(f"  ...{i+1}/{len(targets)} (linkedin+{fli} twitter+{ftw} email+{fem})")
        time.sleep(sleep)

    # rebuild union snapshots for affected repos (cache edits must propagate)
    if slugs is None:
        slugs = [json.load(open(os.path.join(d, "repo.json")))["repo"]
                 for d in glob.glob(os.path.join(config.CACHE, "repos", "*"))
                 if os.path.exists(os.path.join(d, "repo.json"))]
    for slug in slugs:
        rebuild_combined(slug)
    print(f"\nDONE: linkedin+{fli} twitter+{ftw} email+{fem} | rebuilt {len(slugs)} repo union(s)")
    return fli, ftw, fem
