# github-stargazer → ICP-qualified CRM

Turn the people who **starred or forked** a GitHub repo into a segmented, ICP-qualified CRM:
**B-end** (target companies) and **C-end** (high-potential individual AI builders). Runs on
public GitHub (no token needed; a token unlocks full coverage). Input is an **ICP + one or
more repos**; output is one clean folder per `(repo × ICP)`.

```
input:  icps/<icp>.md  +  one or more owner/repo
            │
  fetch stars + forks ─▶ enrich profiles (shared cache) ─▶ [--website crawl] ─▶ [deepline] ─▶ score against ICP
            │                                                                                │
            └──────────────────────────────────────────────────────────────────  runs/<repo>/<icp>/
                                                                                     ├─ bend_company_feed.csv   (B-end → your enrichment)
                                                                                     ├─ cend_individuals.csv    (C-end + contacts)
                                                                                     ├─ gtm_crm.xlsx            (master workbook)
                                                                                     └─ MANIFEST.json / README.md
```

## Quick start

```bash
pip install -r requirements.txt              # only openpyxl (optional); core is stdlib

python app.py icp --init myicp               # scaffold icps/myicp.md from the template, then edit it
python app.py run OWNER/REPO --icp myicp --token $GITHUB_TOKEN
open runs/OWNER__REPO/myicp/README.md        # tells you what each output is
```

Multiple repos in one go: `python app.py run a/b c/d e/f --icp myicp` (or list them in `repos.txt`).

## How identity & caching work (the product model)

- **`.cache/profiles/<login>.json`** — a GitHub profile, **shared across every repo and ICP**. The
  expensive scrape happens once per person; a new repo only fetches people you've never seen.
- **`.cache/repos/<owner__repo>/`** — that repo's seeds (`stargazers.json`, `forkers.json`) + a
  `union.json` snapshot. Per-repo, ICP-independent.
- **`.cache/verdicts/<icp>.json`** — research verdicts for an ICP, keyed by company, reused across repos.
- **`runs/<owner__repo>/<icp>/`** — the deliverables for one `(repo × ICP)` pair. Safe to delete & regenerate.

A **new ICP on the same repo just re-scores** — no re-scrape: `python app.py score <repo> --icp <new>`.

## Commands

| command | what it does |
|---|---|
| `run <repos…> --icp <id> [--token][--website][--deepline]` | pipeline (website crawl is opt-in via --website) |
| `score <repo> --icp <id>` | re-score against an ICP, **zero network** (joins verdicts) |
| `rescore --icp <id> [repos…]` | fan a swapped ICP across already-scraped repos |
| `status [--repo X][--icp Y]` | show `fresh / re-score / re-scrape` per `(repo,ICP)` |
| `icp --init <id>` / `icp --path <id>` | scaffold / validate an ICP file |
| `fetch`, `fetch-forks`, `enrich`, `website`, `find-linkedin`, `merge-linkedin` | individual stages |

## B-end vs C-end

Every lead lands in exactly one bucket:
- **B-end (B端目标客户公司)** — has a *real* company (placeholders/locations like `Remote`, `Beijing`
  filtered; a LinkedIn-verified company always counts) and the company matches your ICP. The deliverable
  is **`bend_company_feed.csv`** — a deduplicated company list (`company, icp_verdict, lead_count, best_rank`)
  to feed your own company-enrichment.
- **C-end (C端高潜个人用户)** — no real company, but a high-potential individual (AI/ML focus, ICP signal,
  followers, or real repos). Here a name + contact is the unit → `cend_individuals.csv` + `linkedin_to_scrape.csv`.

Forking ranks **above** starring (stronger intent); `gtm_grade` (A/B/C) is an absolute, deterministic grade
combining ICP match + source weight + signals. Researched verdicts (Tier A / Yellow / Channel / Supplier /
Scout / DQ) sort the B-end so the real targets are on top.

## The ICP file & two-pass scoring

`icps/<id>.md` is markdown and tolerant (headings matched by keyword, `!`-bullets are exclusions, a
`Weights` section; see [icps/_template.md](icps/_template.md)). A missing/garbage file → neutral mode (still
ranks by source + signals). The decisive B-end calls (*competitor? fixed-protocol agent? which memory value?*)
need per-company **web research**, which is a separate step:

1. `run` / `score` → `bend_company_feed.csv` (verdict columns blank on the first pass).
2. Research the companies against your ICP (any LLM research pass) → writes `.cache/verdicts/<id>.json` (a `{vnorm(company): verdict}` dict).
3. `score <repo> --icp <id>` → re-joins verdicts into the CRM (zero network).

## Coverage & LinkedIn

- No token → GitHub caps anonymous stargazer pagination at ~960 most-recent; a `GITHUB_TOKEN` uses the API for the full list.
- LinkedIn, cheapest first: GitHub-listed (free) → personal-site crawl (free) → `find-linkedin` via deepline (paid, optional).
- `linkedin_to_scrape.csv` feeds the companion logged-in [LinkedIn_Profile_Scraper](https://github.com/JadeeeZh/LinkedIn_Profile_Scraper); `merge-linkedin --repo <r> --icp <i> results.json` folds verified titles/companies back in.

## Caveats
- Public star/fork lists carry bots, placeholder companies, and individual hobbyists; scoring pushes real leads up — eyeball the top before outreach.
- Everything reads only public GitHub. LinkedIn deep-scrape is gated behind *your* login in the separate tool.

See [AGENTS.md](AGENTS.md) to drive this with an AI agent, [FIELDS.md](FIELDS.md) for every output
column, and [LEARNINGS.md](LEARNINGS.md) for what to expect (B-end is thin, forkers ≫ stargazers,
the grade isn't ICP fit, etc.). Bring your own `icps/<id>.md` (start from [icps/_template.md](icps/_template.md)).
