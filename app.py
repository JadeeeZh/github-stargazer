#!/usr/bin/env python3
"""github-stargazer — turn a repo's stargazers + forkers into an ICP-qualified CRM.

Product flow (input = an ICP + one or more repos):

  python app.py icp --init myicp           # scaffold icps/myicp.md, then edit it
  python app.py run OWNER/REPO --icp myicp --token $GITHUB_TOKEN
  # ... research the B-end companies against your ICP (any LLM research pass) ...
  python app.py score OWNER/REPO --icp myicp       # zero-network re-score, joins verdicts

Identity = (repo, icp). Outputs live in runs/<owner__repo>/<icp>/ with a MANIFEST + README.
The GitHub profile cache (.cache/profiles/) is shared across ALL repos. See AGENTS.md.
"""
import argparse
import os
import sys


def _read_repos_file(path):
    out = []
    for line in open(path, encoding="utf-8"):
        s = line.split("#", 1)[0].strip()
        if s:
            out.append(s)
    return out


def _resolve_repos(positional, repos_file):
    from stargazer import config
    if positional and repos_file:
        raise SystemExit("pass repos positionally OR via --repos, not both")
    if positional:
        return positional
    if repos_file:
        return _read_repos_file(repos_file)
    default = os.path.join(config.ROOT, "repos.txt")
    if os.path.exists(default):
        return _read_repos_file(default)
    raise SystemExit("no repos given (positional, --repos FILE, or a repos.txt at repo root)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="app.py", description="GitHub stargazers + forkers -> ICP CRM")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("run", help="full pipeline: fetch stars+forks -> enrich -> website -> [deepline] -> score")
    sp.add_argument("repos", nargs="*", help="owner/repo ... (or use --repos / repos.txt)")
    sp.add_argument("--repos", dest="repos_file", default=None, help="file with one owner/repo per line")
    sp.add_argument("--icp", default=None, help="ICP id (icps/<id>.md) or a path; default = sole ICP")
    sp.add_argument("--limit", type=int, default=100000)
    sp.add_argument("--token", default=None, help="GitHub token (or env GITHUB_TOKEN)")
    sp.add_argument("--deepline", action="store_true", help="also resolve LinkedIn via deepline (paid)")
    sp.add_argument("--refresh-seeds", action="store_true", help="re-fetch stargazers/forkers even if cached")
    sp.add_argument("--sleep", type=float, default=0.4)

    sp = sub.add_parser("score", help="re-score a repo against an ICP (zero network); joins verdicts")
    sp.add_argument("repo")
    sp.add_argument("--icp", default=None)

    sp = sub.add_parser("rescore", help="re-score an ICP across already-scraped repos")
    sp.add_argument("repos", nargs="*", help="repos (default: all cached)")
    sp.add_argument("--icp", default=None)

    sp = sub.add_parser("status", help="show fresh / re-score / re-scrape per (repo,ICP)")
    sp.add_argument("--repo", default=None)
    sp.add_argument("--icp", default=None)

    sp = sub.add_parser("fetch", help="collect stargazers for a repo")
    sp.add_argument("repo"); sp.add_argument("--limit", type=int, default=100000)
    sp.add_argument("--token", default=None); sp.add_argument("--sleep", type=float, default=0.7)

    sp = sub.add_parser("fetch-forks", help="collect forkers for a repo")
    sp.add_argument("repo"); sp.add_argument("--limit", type=int, default=100000)
    sp.add_argument("--token", default=None); sp.add_argument("--sleep", type=float, default=0.7)

    sp = sub.add_parser("enrich", help="scrape missing profiles for a repo into the shared cache")
    sp.add_argument("repo"); sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--sleep", type=float, default=0.4)

    sp = sub.add_parser("website", help="crawl personal sites for LinkedIn/contact (shared cache)")
    sp.add_argument("repos", nargs="*", help="repos whose unions to rebuild (default: all cached)")
    sp.add_argument("--sleep", type=float, default=0.5)

    sp = sub.add_parser("find-linkedin", help="resolve LinkedIn for a repo's A/B leads via deepline (optional)")
    sp.add_argument("repo"); sp.add_argument("--min-priority", default="B", choices=["A", "B"])
    sp.add_argument("--max", type=int, default=60, dest="max_lookups")
    sp.add_argument("--loose", action="store_true"); sp.add_argument("--sleep", type=float, default=0.5)

    sp = sub.add_parser("merge-linkedin", help="merge LinkedIn_Profile_Scraper results into a run")
    sp.add_argument("results", help="path to the scraper's results.json")
    sp.add_argument("--repo", required=True); sp.add_argument("--icp", default=None)

    sp = sub.add_parser("icp", help="validate an ICP (or scaffold one with --init <id>)")
    sp.add_argument("--path", default=None, help="ICP id or path to validate")
    sp.add_argument("--init", default=None, metavar="ID", help="scaffold icps/<ID>.md from the template")

    args = p.parse_args(argv)
    from stargazer import config

    if args.cmd == "run":
        from stargazer import fetch, forks, enrich, website, crm
        repos = _resolve_repos(args.repos, args.repos_file)
        _, icp_id = config.resolve_icp(args.icp)
        scraped = {}
        for slug in repos:
            rp = config.repo_paths(slug)
            if args.refresh_seeds or not os.path.exists(rp["stargazers"]):
                fetch.run(slug, limit=args.limit, token=args.token, sleep=max(args.sleep, 0.7))
            else:
                print(f"[{slug}] reusing cached stargazers (--refresh-seeds to re-fetch)")
            if args.refresh_seeds or not os.path.exists(rp["forkers"]):
                forks.run(slug, limit=args.limit, token=args.token, sleep=max(args.sleep, 0.7))
            else:
                print(f"[{slug}] reusing cached forkers")
            _, n = enrich.run(slug, sleep=args.sleep, limit=args.limit)
            scraped[slug] = n
        website.run(slugs=repos, sleep=max(args.sleep, 0.4))
        for slug in repos:
            if args.deepline:
                from stargazer import deepline_lookup
                deepline_lookup.run(slug, min_priority="B")
            crm.run_gtm(slug, icp_id, scraped_this_run=scraped.get(slug, 0))

    elif args.cmd == "score":
        from stargazer import crm
        _, icp_id = config.resolve_icp(args.icp)
        crm.run_gtm(args.repo, icp_id)

    elif args.cmd == "rescore":
        from stargazer import crm
        import glob
        _, icp_id = config.resolve_icp(args.icp)
        import json
        repos = args.repos or [json.load(open(os.path.join(d, "repo.json")))["repo"]
                               for d in glob.glob(os.path.join(config.CACHE, "repos", "*"))
                               if os.path.exists(os.path.join(d, "repo.json"))]
        for slug in repos:
            crm.run_gtm(slug, icp_id)

    elif args.cmd == "status":
        _status(config, args.repo, args.icp)

    elif args.cmd == "fetch":
        from stargazer import fetch
        fetch.run(args.repo, limit=args.limit, token=args.token, sleep=args.sleep)
    elif args.cmd == "fetch-forks":
        from stargazer import forks
        forks.run(args.repo, limit=args.limit, token=args.token, sleep=args.sleep)
    elif args.cmd == "enrich":
        from stargazer import enrich
        enrich.run(args.repo, sleep=args.sleep, limit=args.limit)
    elif args.cmd == "website":
        from stargazer import website
        website.run(slugs=(args.repos or None), sleep=args.sleep)
    elif args.cmd == "find-linkedin":
        from stargazer import deepline_lookup
        deepline_lookup.run(args.repo, min_priority=args.min_priority,
                            max_lookups=args.max_lookups, sleep=args.sleep, loose=args.loose)
    elif args.cmd == "merge-linkedin":
        from stargazer import merge_linkedin
        _, icp_id = config.resolve_icp(args.icp)
        merge_linkedin.run(args.results, args.repo, icp_id)
    elif args.cmd == "icp":
        _icp_cmd(config, args)
    return 0


def _icp_cmd(config, args):
    from stargazer import icp
    import shutil
    if args.init:
        icp_id = args.init.lower()
        assert config.ICP_RE.match(icp_id), f"bad icp id {icp_id!r} (allowed: a-z 0-9 _ -)"
        os.makedirs(config.ICPS_DIR, exist_ok=True)
        dest = os.path.join(config.ICPS_DIR, f"{icp_id}.md")
        tmpl = os.path.join(config.ICPS_DIR, "_template.md")
        if os.path.exists(dest):
            print("exists, not overwriting:", dest)
        elif os.path.exists(tmpl):
            shutil.copy(tmpl, dest); print("wrote", dest)
        else:
            print("template missing:", tmpl)
        return
    icp_path, _ = config.resolve_icp(args.path)
    obj = icp.load(icp_path)
    print(f"loaded={obj.loaded} path={obj.path or '(none)'}")
    print(f"  B keywords={len(obj.b_keywords)} excl={len(obj.b_exclude)} | "
          f"C keywords={len(obj.c_keywords)} excl={len(obj.c_exclude)}")
    print(f"  seniority={len(obj.seniority)} global-excl={len(obj.exclude)} weights={obj.weights}")
    if obj.warnings:
        print("  warnings:", obj.warnings)


def _status(config, only_repo, only_icp):
    import glob
    import hashlib
    import json
    rows = []
    for mpath in glob.glob(os.path.join(config.RUNS, "*", "*", "MANIFEST.json")):
        try:
            m = json.load(open(mpath, encoding="utf-8"))
        except Exception:
            continue
        if only_repo and m.get("repo") != only_repo:
            continue
        if only_icp and m.get("icp", {}).get("id") != only_icp:
            continue
        state = "fresh"
        icp_path = m.get("icp", {}).get("path", "")
        try:
            cur = hashlib.sha256(open(icp_path, "rb").read()).hexdigest() if icp_path else ""
            if cur and cur != m.get("icp", {}).get("sha256"):
                state = "re-score (ICP changed)"
        except Exception:
            pass
        rp = config.repo_paths(m["repo"])
        if not os.path.exists(rp["union"]):
            state = "re-scrape (no union)"
        else:
            try:
                meta = json.load(open(rp["repo_json"], encoding="utf-8"))
                if meta.get("last_enriched_at", "") > m.get("generated_at", ""):
                    state = "re-score (cache grew)"
            except Exception:
                pass
        rows.append((m["run_id"], state, m.get("counts", {}).get("b_companies_distinct", "?")))
    if not rows:
        print("no runs yet."); return
    print(f"{'run_id':40} {'state':24} b_companies")
    for rid, st, n in sorted(rows):
        print(f"{rid:40} {st:24} {n}")


if __name__ == "__main__":
    sys.exit(main())
