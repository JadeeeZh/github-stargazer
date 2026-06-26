# AGENTS.md — driving github-stargazer with an AI agent

This is a small CLI product: **input = an ICP + one or more GitHub repos → output = an
ICP-qualified CRM** (B-end target companies + C-end individual builders), one folder per
`(repo × ICP)`. It's runnable by a human or an agent. Everything is resumable and writes
only under `.cache/` and `runs/`.

## TL;DR

```bash
pip install -r requirements.txt
python app.py icp --init <id>                 # then edit icps/<id>.md
python app.py run <owner/repo> [more…] --icp <id> [--token $GITHUB_TOKEN]
# read runs/<owner__repo>/<id>/README.md  (it says what each file is for)
```

Then report the B-end Tier-A/Yellow targets and the C-end grade-A builders.

## The identity & cache model (internalize this)

A unit of work is **`(repo_slug, icp_id)`**. `repo_key = owner/repo → owner__repo` (one-way; the
verbatim slug lives in `repo.json`/`MANIFEST.json`). `icp_id` = ICP filename stem.

Three zones (see `stargazer/config.py`):
- **`.cache/profiles/<login>.json`** — GitHub profile, **shared across all repos & ICPs**. The
  expensive scrape; never per-repo. A new repo only scrapes logins not already here.
- **`.cache/repos/<repo_key>/`** — per-repo seeds + `union.json` (stars∪forks snapshot). ICP-independent.
- **`.cache/verdicts/<icp_id>.json`** — research verdicts, keyed by `_vnorm(company)`, reused across repos.
- **`runs/<repo_key>/<icp_id>/`** — deliverables; safe to delete & regenerate from cache.

## Decisions to surface

- **Scale / token.** No token → GitHub caps anonymous stargazers at ~960; tell the user to set
  `GITHUB_TOKEN` for full coverage. A big enrich runs in the background.
- **New ICP = re-score, not re-scrape.** `score <repo> --icp <new>` is network-free. Use it.
- **B-end deliverable is the company NAME** (`bend_company_feed.csv`) — the user enriches companies
  downstream, so do NOT chase per-person contacts for B-end. Contacts matter only for **C-end**.
- **Deepline (`find-linkedin`) and the LinkedIn scraper cost money / credentials — ask first.**
- **B-end qualification needs web research** (competitor? fixed-protocol? memory value?) — keyword
  matching only pre-filters. Run the research pass, write verdicts, then `score` again.
- **Gate research by `company_status`, not by name-blacklisting.** The feed proves "is it a real
  company" from free signals (domain / `/company/` LinkedIn / non-free email / ≥2 leads / domain-like
  name) → proven / to-verify / unproven. Research **proven + to-verify + AI-focused unproven**, skip the
  rest — that kills the junk long tail cheaply. But `unproven` is a *flag, not a drop*: a real stealth
  startup can be unproven (no public footprint), so don't auto-discard AI-relevant ones.
- **GitHub stars/forks are a *developer* signal, not a *company* signal** — so a chunk of B-end "companies"
  are individuals' bio fragments or mascots. For a higher-precision company funnel, source from a company
  DB (Crunchbase/LinkedIn-company/your TAM) and use GitHub as *enrichment* on those, rather than as the entry.

## Invariants — do NOT break when extending

1. **Profile cache is shared & ICP-/repo-independent.** Source/rank are joined at build from seed files
   via `stargazer/seed.py` (`load_seeds(slug)`); never store provenance in `.cache/profiles/`.
2. **Cached `rank` is untrusted** (fork-only profiles hold fork ranks). `enrich.rebuild_combined(slug)`
   re-stamps `best_rank` from seeds; GTM sorts on `best_rank`, never cached `rank`.
3. **`score` is zero-network**: it rebuilds `union.json` from the local cache (which reflects
   website/merge/deepline edits) and never calls `enrich.run`. Only `enrich.run` stamps
   `repo.json.last_enriched_at` (the staleness signal `status` reads).
4. **`gtm_grade` ≠ legacy priority** — absolute thresholds (A≥9/B≥5 in `icp.py`). Fork>star is guaranteed
   (`seed.SOURCE_WEIGHT` both=3/fork=2/star=1 + `SOURCE_ORDER` tiebreak).
5. **`icp.load()` never raises** — missing/garbage ICP ⇒ neutral matcher (`loaded=False`).
6. **Outputs are path-namespaced**, never filename-prefixed — `runs/<repo_key>/<icp_id>/` + a `MANIFEST.json`
   (machine) + generated `README.md` (human; `files[].role` is the authoritative "send where").
7. **Verdicts stay a single dict per ICP** keyed by `_vnorm(company)` — the qualifier merges into it.

## Companion tool

LinkedIn deep-enrichment is intentionally separate (needs your login):
[LinkedIn_Profile_Scraper](https://github.com/JadeeeZh/LinkedIn_Profile_Scraper). Feed it
`runs/<repo_key>/<icp_id>/linkedin_to_scrape.csv`, then `merge-linkedin --repo <r> --icp <i> results.json`.
Bring your own ICP — copy `icps/_template.md` to `icps/<id>.md` and edit. The B-end research
step (step 2 of the two-pass loop) is any LLM pass that reads `bend_company_feed.csv` and writes
`{vnorm(company): verdict}` into `.cache/verdicts/<id>.json`.
