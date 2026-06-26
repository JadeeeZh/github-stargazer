"""Paths and identity for the productized GTM tool.

Three zones, by lifetime + sharing:
  ZONE 1  .cache/profiles/<login>.json  — GitHub profile, shared across ALL repos & ICPs (expensive)
  ZONE 2  .cache/repos/<repo_key>/      — per-repo seeds (stargazers/forkers) + union snapshot
          .cache/verdicts/<icp_id>.json — per-ICP research verdicts (shared across repos)
  ZONE 3  runs/<repo_key>/<icp_id>/      — per-(repo,ICP) deliverables; safe to delete & regenerate

Identity = (repo_slug, icp_id). repo_key is a ONE-WAY token (never reverse-parsed; the
verbatim slug is carried in repo.json / MANIFEST.json for display). icp_id = ICP filename stem.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache")
PROFILES = os.path.join(CACHE, "profiles")
PROFILES_INDEX = os.path.join(CACHE, "profiles_index.json")
ICPS_DIR = os.path.join(ROOT, "icps")
RUNS = os.path.join(ROOT, "runs")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

ICP_RE = re.compile(r"^[a-z0-9_-]+$")


def repo_key(slug):
    """owner/repo -> owner__repo. ONE-WAY (repo names may contain '_'); never reverse-parse."""
    key = slug.strip("/").replace("/", "__")
    assert "/" not in key and ".." not in key, f"unsafe repo key from slug: {slug!r}"
    return key


def profile_path(login):
    return os.path.join(PROFILES, f"{login}.json")


def repo_paths(slug):
    d = os.path.join(CACHE, "repos", repo_key(slug))
    return {"dir": d,
            "stargazers": os.path.join(d, "stargazers.json"),
            "forkers": os.path.join(d, "forkers.json"),
            "union": os.path.join(d, "union.json"),
            "repo_json": os.path.join(d, "repo.json")}


def verdicts_file(icp_id):
    return os.path.join(CACHE, "verdicts", f"{icp_id}.json")


def _sole_icp_id():
    cands = [os.path.splitext(os.path.basename(p))[0].lower()
             for p in glob.glob(os.path.join(ICPS_DIR, "*.md"))]
    cands = [c for c in cands if c != "_template" and not c.endswith(".example")]
    if len(cands) == 1:
        return cands[0]
    raise SystemExit(f"--icp required; choices in icps/: {sorted(cands) or '(none)'}")


def resolve_icp(arg):
    """-> (path, icp_id). arg may be an id ('myicp') or a path ('./foo.md'); None -> sole ICP."""
    is_path = bool(arg) and (("/" in arg) or arg.endswith(".md"))
    icp_id = (os.path.splitext(os.path.basename(arg))[0].lower() if is_path
              else (arg or _sole_icp_id()).lower())
    assert ICP_RE.match(icp_id), f"bad icp_id {icp_id!r} (allowed: a-z 0-9 _ -)"
    path = arg if is_path else os.path.join(ICPS_DIR, f"{icp_id}.md")
    return path, icp_id


def run_paths(slug, icp_id):
    d = os.path.join(RUNS, repo_key(slug), icp_id)
    r = os.path.join(d, "research")
    return {"dir": d, "research_dir": r, "scratch_dir": os.path.join(r, "_scratch"),
            "manifest": os.path.join(d, "MANIFEST.json"), "readme": os.path.join(d, "README.md"),
            "csv": os.path.join(d, "gtm_crm.csv"), "xlsx": os.path.join(d, "gtm_crm.xlsx"),
            "csv_b": os.path.join(d, "bend_companies.csv"),
            "csv_company_feed": os.path.join(d, "bend_company_feed.csv"),
            "csv_c": os.path.join(d, "cend_individuals.csv"),
            "linkedin_csv": os.path.join(d, "linkedin_to_scrape.csv"),
            "verdicts_csv": os.path.join(r, "verdicts.csv"),
            "targets_md": os.path.join(r, "targets.md")}


def ensure_dirs():
    for d in (CACHE, PROFILES, os.path.join(CACHE, "repos"),
              os.path.join(CACHE, "verdicts"), RUNS):
        os.makedirs(d, exist_ok=True)


def ensure_run_dirs(slug, icp_id):
    p = run_paths(slug, icp_id)
    for d in (PROFILES, repo_paths(slug)["dir"], p["dir"], p["research_dir"], p["scratch_dir"]):
        os.makedirs(d, exist_ok=True)


def tool_version():
    """git short sha -> package __version__ -> 'unknown'. Best-effort, never raises."""
    try:
        import subprocess
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        from . import __version__
        return __version__
    except Exception:
        return "unknown"
