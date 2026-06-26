"""Optional: resolve LinkedIn URLs for high-value leads via the deepline CLI.

For each priority A/B lead that has a real name + company but no LinkedIn yet, run a
Serper Google search scoped to linkedin.com/in, then accept a result only if the
person's name AND company both validate (guards against same-name false positives).
Resolved URLs are written back with linkedin_confidence='medium' (and a note recording
the deepline source) so the downstream LinkedIn_Profile_Scraper can still deep-verify
them while logged in.

Requires the `deepline` CLI on PATH and an authenticated workspace
(`deepline auth status`). Serper costs a fraction of a cent per query; this step is
skipped entirely if deepline is unavailable, so the repo stays usable without it.

Reference: deepline-gtm recipe `linkedin-url-lookup` (serper -> name validation).
"""
import glob, json, os, re, shutil, subprocess, time
from . import config
from .crm import build_leads, disp_company
from .nameval import names_match, looks_like_person, norm
from .enrich import rebuild_combined


def _deepline_available():
    return shutil.which("deepline") is not None


def _run_tool(tool, payload, timeout=70):
    try:
        p = subprocess.run(
            ["deepline", "tools", "execute", tool, "--payload", json.dumps(payload), "--json"],
            capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return None
    out = p.stdout or ""
    i = out.find("{")
    if i < 0:
        return None
    try:
        return json.loads(out[i:])
    except Exception:
        return None


def _deep_find(o, key):
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = _deep_find(v, key)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _deep_find(v, key)
            if r is not None:
                return r
    return None


def _clean_in(url):
    url = (url or "").split("?")[0].rstrip("/")
    m = re.search(r"(https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^/\s\"'>]+)", url, re.I)
    return m.group(1) if m else ""


def _company_token(company):
    """A distinctive token from the company name for snippet matching."""
    stop = {"the", "inc", "llc", "ltd", "corp", "corporation", "company", "co",
            "technologies", "labs", "ai", "io", "group", "global", "and"}
    toks = [t for t in norm(company).split() if t not in stop and len(t) >= 3]
    return toks[0] if toks else ""


def serper_lookup(name, company, loose=False):
    """Return (url, confidence) or (None, None)."""
    q = f'"{name}" "{company}" site:linkedin.com/in' if company else f'"{name}" site:linkedin.com/in'
    res = _run_tool("serper_google_search", {"query": q, "num": 5})
    if not res:
        return None, None
    organic = _deep_find(res, "organic") or []
    ctoken = _company_token(company)
    name_only_hit = None
    for r in organic:
        url = _clean_in(r.get("link", ""))
        if not url:
            continue
        title = r.get("title", "")
        snippet = (title + " " + r.get("snippet", "")).lower()
        # title format: "First Last - Title at Company | LinkedIn"
        cand_name = title.split(" - ")[0].split(" | ")[0].strip()
        if not names_match(name, cand_name):
            continue
        if ctoken and ctoken in snippet:
            return url, "deepline (name+company)"
        if name_only_hit is None:
            name_only_hit = url
    if loose and name_only_hit:
        return name_only_hit, "deepline (name only — verify)"
    return None, None


def run(slug, min_priority="B", max_lookups=60, sleep=0.5, loose=False):
    if not _deepline_available():
        print("deepline CLI not found on PATH — skipping LinkedIn resolution.")
        print("  install + authenticate: https://code.deepline.com  (then `deepline auth register`)")
        return []
    records = json.load(open(config.repo_paths(slug)["union"], encoding="utf-8"))
    by_login = {r["login"]: r for r in records}
    leads, _ = build_leads(records)

    allowed = {"A"} if min_priority == "A" else {"A", "B"}
    targets = [l for l in leads
               if l["priority"] in allowed and not l["linkedin"]
               and looks_like_person(l["name"]) and l["company"]]
    targets = targets[:max_lookups]
    print(f"deepline LinkedIn lookup: {len(targets)} priority-{'/'.join(sorted(allowed))} "
          f"leads with name+company but no LinkedIn (cap {max_lookups})")

    found = 0
    for i, l in enumerate(targets):
        url, conf = serper_lookup(l["name"], l["company"], loose=loose)
        if url:
            rec = by_login.get(l["login"])
            if rec is not None:
                rec["linkedin_url"] = url
                rec.setdefault("linkedin_confidence", "")
                if rec["linkedin_confidence"] not in ("high",):
                    rec["linkedin_confidence"] = "medium"
                rec["notes"] = ((rec.get("notes", "") or "") + f" | LinkedIn via {conf}").strip(" |")
                with open(config.profile_path(l["login"]), "w", encoding="utf-8") as f:
                    json.dump(rec, f, ensure_ascii=False, indent=2)
                found += 1
                print(f"  + {l['name']} @ {l['company']}  ->  {url}  [{conf}]")
        if (i + 1) % 10 == 0:
            print(f"  ...{i+1}/{len(targets)} (found {found})")
        time.sleep(sleep)

    rebuild_combined(slug)
    print(f"\nDONE: resolved {found} new LinkedIn URLs via deepline")
    print("  re-run `score` to refresh the CRM")
    return found
