# ICP — Ideal Customer Profile

<!-- Tolerant format. Headings are matched by KEYWORD (case-insensitive substring); a heading
     that matches TWO section classes is ambiguous -> its bullets are IGNORED with a warning,
     so keep headings single-purpose. Bullets are signals; a bullet starting with "!" is an
     exclusion. Separate multiple terms with COMMAS (or CJK 、，). Do NOT rely on "/" or " - "
     to split — slashes are kept literally (so "AI/ML" stays one term). Weights live ONLY in
     the Weights section as "weight <key>: N" (0-5). A missing/empty/garbage file => neutral
     mode: the pipeline still ranks by source weight + existing signals. -->

<!-- Copy this file to icps/<your-id>.md and replace the EXAMPLE bullets below with your
     own ICP. The examples here are AI-flavored for illustration — swap in your industry. -->

## Product
One or two sentences on what you sell. (Low-weight context.)

## B-end Target Companies (B端目标客户公司)
<!-- keywords matched on heading: b-end, b端, b2b, target compan, account, 目标客户, 公司 -->
- AI, LLM, agent infrastructure companies
- developer tools, MLOps, platform engineering
- seed to Series-C startups, 10-500 employees
- keywords: agent, llm, rag, memory, vector, copilot, mcp, inference, devtools, infra
- ! agency, ! consultancy, ! reseller, ! outsourcing

## C-end High-Potential Individuals (C端高潜个人用户)
<!-- keywords matched on heading: c-end, c端, individual, persona, indie, 个人, 高潜 -->
- builds AI agents, LLM apps, RAG, memory systems
- active OSS contributor, strong GitHub presence
- AI ML engineer, researcher, indie hacker, founder
- keywords: agent, llm, rag, langchain, autogen, crewai, vector, fine-tune

## Target Seniority
- founder, co-founder, ceo, cto, vp engineering, head of ai, head of product, staff, principal

## Exclusions (排除)
<!-- applies to BOTH buckets; matched leads are demoted to grade C, never deleted -->
- ! bot, ! recruiter, ! sales, ! spam, ! course, ! bootcamp

## Weights
<!-- 0-5, clamped. Source weight is fixed in code (both=3 fork=2 star=1). -->
- weight icp: 3
- weight ai_focus: 3
- weight seniority: 2
- weight recency: 1
- weight identifiability: 1
