"""Merge LinkedIn_Profile_Scraper results back into the stargazer enrichment.

The scraper writes results.json with fields: profile_url, full_name, headline,
latest_1_experience_title/company, highest_degree_detected, status. We map each
profile_url back to its GitHub login via the candidate_id in the run's
linkedin_to_scrape.csv (runs/<repo_key>/<icp_id>/), write the LinkedIn fields into the
shared profile cache (confidence='high' — a real logged-in read), then rebuild the union.
"""
import csv, json, os, re
from . import config
from .enrich import rebuild_combined


def _slug(url):
    m = re.search(r"/(?:in|pub|company)/([^/?#]+)", url or "", re.I)
    return (m.group(1) if m else (url or "")).rstrip("/").lower()


def parse_headline(hl):
    """Pull (title, company) from a LinkedIn headline like 'Title at/@/de Company'.

    Used when the structured experience section didn't parse. Conservative: only
    fires on an explicit at/@/de separator; returns ('', '') otherwise.
    """
    hl = (hl or "").strip()
    if not hl or "skip to" in hl.lower():
        return "", ""
    m = re.search(r"(.*?)\s*(?:@|\bat\b|\bde\b)\s+([A-Za-z0-9][^|·•]*)", hl, re.I)
    if not m:
        return "", ""
    title = m.group(1).strip(" |·•-")
    company = re.split(r"[|·•,;(]", m.group(2))[0].strip()
    company = re.sub(r"\b(global|inc|llc|ltd)\.?$", "", company, flags=re.I).strip()
    if len(company) > 45 or len(company) < 2:
        company = ""
    # a leading "@handle" with no space (e.g. "@SHEIN") — recover it
    if not company:
        m2 = re.search(r"@([A-Za-z0-9][\w.-]{1,40})", hl)
        if m2:
            company = m2.group(1)
            title = hl.split("@")[0].strip(" |·•-")
    return title[:80], company


def run(results_path, slug, icp_id):
    results = json.load(open(results_path, encoding="utf-8"))
    url2login = {}
    li_csv = config.run_paths(slug, icp_id)["linkedin_csv"]
    with open(li_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("profile_url") and row.get("candidate_id"):
                url2login[_slug(row["profile_url"])] = row["candidate_id"]

    merged = skipped = 0
    for s in results:
        login = url2login.get(_slug(s.get("profile_url", "")))
        fp = config.profile_path(login) if login else None
        if not fp or not os.path.exists(fp):
            skipped += 1
            continue
        headline = s.get("headline", "")
        got = s.get("full_name") or s.get("latest_1_experience_title") or \
            (headline and "skip to" not in headline.lower())
        if s.get("status") not in ("success", "partial") and not got:
            skipped += 1
            continue
        r = json.load(open(fp, encoding="utf-8"))
        if s.get("full_name"):
            r["linkedin_name"] = s["full_name"]
        if headline and "skip to" not in headline.lower():
            r["linkedin_headline"] = headline
        if s.get("latest_1_experience_title"):
            r["linkedin_title"] = s["latest_1_experience_title"]
        if s.get("latest_1_experience_company"):
            r["linkedin_company"] = s["latest_1_experience_company"]
        # fall back to the headline when the structured experience section is empty
        if not r.get("linkedin_company") and headline:
            ht, hc = parse_headline(headline)
            if hc:
                r["linkedin_company"] = hc
                r["notes"] = ((r.get("notes", "") or "") + " | company from LinkedIn headline").strip(" |")
            if ht and not r.get("linkedin_title"):
                r["linkedin_title"] = ht
        if s.get("highest_degree_detected"):
            r["linkedin_education"] = s["highest_degree_detected"]
        r["linkedin_confidence"] = "high" if (s.get("full_name") or s.get("latest_1_experience_title")) else "medium"
        r["notes"] = ((r.get("notes", "") or "") + " | LinkedIn deep-scrape (logged-in)").strip(" |")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        merged += 1

    rebuild_combined(slug)
    print(f"merged {merged} LinkedIn profiles | skipped {skipped}")
    print(f"now run `score {slug} --icp {icp_id}` to refresh the CRM")
    return merged
