# Learnings — what running this on a real repo taught us

Patterns observed running the full pipeline (stars + forks + ICP + multi-batch research)
on a ~9k-star repo. They're baked into the defaults; here's the *why* so you can trust the
fields and not redo work.

## 1. GitHub stars/forks are a *developer* signal, not a *company* signal
Thousands of stargazers/forkers yield only a **handful** of real B-end company targets — the
long tail is individuals, mascots, wrong-industry, and placeholder "companies." Don't expect a
B-end pipeline proportional to star count. The **dense, warm pool is C-end** (individual builders).
The root fix for a high-precision *company* funnel is to source from a company DB and use GitHub as
enrichment — not as the entry (noted in AGENTS.md).

## 2. Forkers ≫ stargazers
Forking means they took the code and (probably) ran it — real intent. Forkers are the best **user-
interview** subjects and the strongest leads. Source weight is fixed `both=3 / fork=2 / star=1`, and
`cend_shortlist.csv` ranks forkers first.

## 3. The keyword grade is decoupled from ICP fit — never gate on it
`gtm_grade` / `best_grade` (A≥9, B≥5) measure GitHub activity + AI-keyword density, **not** whether a
company is a buyable ICP fit (a university scored "A"). Use it only as a C-end *builder* signal. The
real B-end judgment is the **researched `icp_verdict`**, nothing else.

## 4. "Prove it's a real company" beats blacklisting names
Junk names are an infinite long tail; a blacklist never catches up. Instead require **evidence**
(real domain / `/company/` LinkedIn / non-free email / ≥2 leads / domain-like name) →
`company_status` proven/to-verify/unproven. **But it's a flag, not a hard drop:** a real stealth
startup can score 0 evidence (no public footprint), so AI-focused unproven candidates still get
researched. Pure unproven-non-AI is the skippable junk.

## 5. `research_status` is the single gate — stop re-deriving shortlists
Every B-end company carries `research_status` ∈ **research / done / auto-dq / skip**. "What to
research next" is just `research_status == "research"` — no manual shortlist rebuilding, no
re-researching (verdicts are cached in `.cache/verdicts/<icp>.json`, keyed by company). When that
bucket hits 0, the repo is exhausted for B-end.

## 6. Normalize text at ingestion
GitHub HTML leaves entities (`&amp;`, `&#39;`) in names/companies — they broke the company-name
verdict join and mangled display. `enrich` now `html.unescape`s on the way in. Company-name as a
join key is still fragile (spelling variants like "Adminstration"); dedup by normalized name and
accept a little slippage.

## 7. Research has sharp diminishing returns — batch by priority
Across three research batches the first (recent/high-signal) carried almost all the targets; the
tail was ~all DQ/not-a-company. Research **proven + to-verify + AI-focused unproven** and stop;
don't grind the unproven-non-AI tail.

## Default thresholds (all in code; change deliberately)
| knob | value | where |
|---|---|---|
| grade A / B floor | score ≥ 9 / ≥ 5 | `icp.GRADE_A_FLOOR` / `GRADE_B_FLOOR` |
| evidence → status | ≥2 proven · 1 to-verify · 0 unproven | `icp.evidence_status` |
| research cutoff | `research_status == research` (candidate + evidence≥1 **or** AI-focused) | `crm._research_status` |
| C-end shortlist | AI/ML focus **or** grade A; ranked forker→reachable→recent | `crm._cend_shortlist` |
| source weight | both 3 / fork 2 / star 1 | `seed.SOURCE_WEIGHT` |
