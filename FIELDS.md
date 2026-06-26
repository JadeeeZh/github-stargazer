# Field dictionary

What every column means in the output files under `runs/<owner__repo>/<icp>/`.

> **The one thing to remember:** there are **two independent grading systems**.
> - `best_grade` / `gtm_grade` = the **automatic keyword grade** (code, no research).
> - `icp_verdict` = the **researched judgment** (web research per your ICP).
> A company can be `best_grade: A` but `icp_verdict: Disqualified` — the keywords looked
> AI-relevant, the research found it isn't a fit. **Trust `icp_verdict` over `best_grade`.**
> Everything else (`category`, `rank`) is triage or recency, not quality.

---

## `bend_company_feed.csv` — the B-end deliverable (one row per company)

Deduplicated company list to feed your own company-enrichment. Sorted so researched, in-ICP
targets sit on top.

| field | meaning |
|---|---|
| **company** | the company's display name (best/most-recent lead's value). |
| **category** | coarse *type* triage on the name: **candidate** (real-ish company, worth pursuing/researching) · **academic** (university/school/institute → usually not an agent company) · **bigtech** (Microsoft/Tencent/… → builds its own; the person is a champion, not an account) · **junk** (placeholder/garbled string). |
| **icp_verdict** | the **researched** verdict (blank = not yet researched). See the table below. |
| **memory_value** | which value the fit hangs on (only meaningful for Tier A / Yellow): **User** (knows the person), **Agent** (gets better with use), **Shared** (team knowledge), **User+Agent**, or **none**. |
| **best_grade** | the **automatic** keyword grade (A/B/C) — the best among this company's people. A≥9, B≥5, else C (score = ICP-keyword match + source weight + AI-focus + seniority + identifiability + recency). |
| **lead_count** | how many people from this company starred/forked the repo. |
| **best_rank** | recency: the *lowest* (newest) rank among the company's people. **1 = most recent** star/fork; higher = older. Lower is fresher, not better. |
| **sources** | how this company's people engaged: `star`, `fork`, `both`, or a combination (e.g. `fork+star`). Forking is stronger intent than starring. |
| **what_they_do** | one line from the research (blank until researched). |
| **lead_with** | the memory pain to open the outreach with (Tier A / Yellow only). |
| **next_action** | suggested move, derived from `icp_verdict` (e.g. "Outreach now + tailored one-pager", "Qualify ICP fit on first call", "Skip"). |

### `icp_verdict` values

| value | meaning → action |
|---|---|
| **Tier A** | real in-ICP buyer → pursue |
| **Yellow flag** | real fit but friction (regulated / owns its data layer) → qualify first |
| **Channel** | SI/consultancy that deploys agents for others → referral/partner, don't sell |
| **Supplier** | compute/inference vendor → at most co-marketing |
| **Scout** | competitor / memory-infra builder → competitive intel, **do NOT sell** |
| **Disqualified** | real company, out of ICP (e.g. pure analytics/BI, not an agent, fixed-protocol eval) |
| **Not a company** | the "company" string is a placeholder / handle / location |
| **Unknown** | couldn't verify the company exists |
| *(blank)* | not yet researched |

---

## `cend_individuals.csv` — high-potential individual builders (one row per person)

People with no real company surfaced but a strong individual signal (AI/ML focus, ICP keyword,
followers, or real repos). Here a name + contact is the unit. Key columns: `name`, `login`,
`segment`, `gtm_grade`, `focus`, `linkedin`, `website`, `twitter`, `email`, `github`, `bio`,
`top_languages`, `notable_repos`, `source`, `rank`.

## `bend_companies.csv` — B-end leads, one row per *person* (not deduped)

Same columns as the CRM plus the joined verdict columns (`icp_verdict`, `memory_value`, `why_fit`,
`lead_with`, `verdict_confidence`, `contact`, `next_action`). Use the **feed** for a clean company
list; use this when you want the underlying people.

## Shared columns (CRM rows)

| field | meaning |
|---|---|
| **rank** | recency for this person — min of their star-rank and fork-rank. **1 = most recent.** |
| **gtm_grade** | automatic A/B/C grade for this person (same formula as `best_grade`). |
| **source** | `star`, `fork`, or `both` for this person. |
| **bucket** | `B` (real company) or `C` (individual). |
| **segment / seniority / company_type / focus** | derived tags from the GitHub profile + (if scraped) LinkedIn. |
| **linkedin_status** | `verified` (logged-in scrape), `found` (a URL we have), or `not listed on GitHub`. |

## `MANIFEST.json` / `README.md`

`MANIFEST.json` is the machine-readable run descriptor (counts, ICP hash, which file to send
where). `README.md` is generated from it — open it first; its file list tells you the role of
each output.
