"""Collect a repo's stargazers, most-recent first.

Two paths:
  - No token  -> scrape public HTML stargazer pages. Free, but GitHub caps
                 anonymous pagination at ~page 40 (~960 most-recent stargazers).
  - With token -> GitHub REST API (Authorization: Bearer <token>), paginates the
                 full list (5,000 req/hr). Pass --token or set GITHUB_TOKEN.
"""
import json, os, re, sys, time
from . import config
from .http import get, get_json

USER_RE = re.compile(r'data-hovercard-url="/users/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})?)/hovercard"')


def _fetch_html(repo, limit, sleep):
    collected, seen, page = [], set(), 1
    while len(collected) < limit:
        html, status = get(f"https://github.com/{repo}/stargazers?page={page}")
        if status != 200 or not html:
            print(f"  stop: page {page} returned {status}", file=sys.stderr)
            break
        new = [m.group(1) for m in USER_RE.finditer(html)]
        new = [u for u in dict.fromkeys(new) if u not in seen]
        if not new:
            print(f"  page {page}: no new users -> end of anonymous pagination", file=sys.stderr)
            break
        for u in new:
            if len(collected) >= limit:
                break
            seen.add(u)
            collected.append({"login": u, "rank": len(collected) + 1})
        print(f"  page {page}: +{len(new)} (total {len(collected)})")
        page += 1
        time.sleep(sleep)
    return collected


def _fetch_api(repo, limit, token, sleep):
    collected, page = [], 1
    headers = {"Authorization": f"Bearer {token}"}
    while len(collected) < limit:
        url = f"https://api.github.com/repos/{repo}/stargazers?per_page=100&page={page}"
        data, status = get_json(url, headers=headers)
        if status != 200 or not data:
            print(f"  stop: API page {page} returned {status}", file=sys.stderr)
            break
        for u in data:
            if len(collected) >= limit:
                break
            login = u.get("login") if isinstance(u, dict) else None
            if login:
                collected.append({"login": login, "rank": len(collected) + 1})
        print(f"  API page {page}: total {len(collected)}")
        if len(data) < 100:
            break
        page += 1
        time.sleep(sleep)
    # API returns oldest-first; flip so rank 1 = most recent
    collected = collected[::-1]
    for i, m in enumerate(collected):
        m["rank"] = i + 1
    return collected


def run(repo, limit=300, token=None, sleep=0.7):
    config.ensure_dirs()
    repo = repo.strip().strip("/")
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        print(f"fetching stargazers via GitHub API (token present) — up to {limit}")
        sg = _fetch_api(repo, limit, token, sleep=max(sleep, 0.1))
    else:
        print(f"fetching stargazers via public HTML (no token) — up to {limit}, "
              f"GitHub caps anonymous pagination at ~960")
        sg = _fetch_html(repo, limit, sleep)
    paths = config.repo_paths(repo)
    os.makedirs(paths["dir"], exist_ok=True)
    with open(paths["stargazers"], "w", encoding="utf-8") as f:
        json.dump({"repo": repo, "count": len(sg), "stargazers": sg}, f,
                  ensure_ascii=False, indent=2)
    print(f"DONE: {len(sg)} stargazers -> {paths['stargazers']}")
    return sg
