"""Collect a repo's forkers, most-recent first. Mirrors fetch.py.

Forking a repo is a stronger intent signal than starring (you actually took the
code), so the GTM pipeline ranks forkers above stargazers.

The forks API with sort=newest is already newest-first -> rank = order, no reversal.
~9 API pages for ~800 forks fits the 60/hr unauthenticated budget; a token raises
that to 5,000/hr. HTML (network/members) is a best-effort fallback only — it is the
fork-network graph and is often truncated, and forked_at is unavailable there.
"""
import json, os, re, sys, time
from . import config
from .http import get, get_json

_HTML_USER_RE = re.compile(
    r'href="/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})?)"[^>]*data-hovercard-type="user"')


def _fetch_api(repo, limit, token, sleep):
    collected, page, partial = [], 1, False
    headers = {"Authorization": f"Bearer {token}"} if token else None
    while len(collected) < limit:
        url = f"https://api.github.com/repos/{repo}/forks?per_page=100&page={page}&sort=newest"
        data, status = get_json(url, headers=headers)
        if status != 200 or not data:
            print(f"  stop: API page {page} returned {status}", file=sys.stderr)
            partial = len(collected) > 0
            break
        for u in data:
            if len(collected) >= limit:
                break
            owner = (u.get("owner") or {}).get("login") if isinstance(u, dict) else None
            if owner:
                collected.append({"login": owner, "rank": len(collected) + 1,
                                  "forked_at": u.get("created_at", "")})
        print(f"  API page {page}: total {len(collected)}")
        if len(data) < 100:
            break
        page += 1
        time.sleep(sleep)
    return collected, partial


def _fetch_html(repo, limit):
    collected, seen = [], set()
    owner = repo.split("/")[0]
    html, status = get(f"https://github.com/{repo}/network/members")
    if status == 200 and html:
        for m in _HTML_USER_RE.finditer(html):
            u = m.group(1)
            if u in seen or u == owner:
                continue
            seen.add(u)
            collected.append({"login": u, "rank": len(collected) + 1, "forked_at": ""})
            if len(collected) >= limit:
                break
    else:
        print(f"  network/members returned {status}", file=sys.stderr)
    return collected


def run(repo, limit=1000, token=None, sleep=0.7):
    config.ensure_dirs()
    repo = repo.strip().strip("/")
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        print(f"fetching forkers via GitHub API (token present) — up to {limit}")
        fk, _ = _fetch_api(repo, limit, token, sleep=max(sleep, 0.1))
    else:
        print(f"fetching forkers via API unauth (60/hr) — up to {limit}; "
              f"HTML fallback only on a clean total failure")
        fk, partial = _fetch_api(repo, limit, None, sleep=max(sleep, 0.7))
        if not fk and not partial:
            print("  API returned nothing; trying HTML fallback (may be truncated)", file=sys.stderr)
            fk = _fetch_html(repo, limit)
    paths = config.repo_paths(repo)
    os.makedirs(paths["dir"], exist_ok=True)
    with open(paths["forkers"], "w", encoding="utf-8") as f:
        json.dump({"repo": repo, "count": len(fk), "forkers": fk}, f, ensure_ascii=False, indent=2)
    print(f"DONE: {len(fk)} forkers -> {paths['forkers']}")
    return fk
