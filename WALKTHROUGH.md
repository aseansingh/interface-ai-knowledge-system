# Understand the project before submitting

## What the company is testing

This is a temporal knowledge and evidence-selection problem. A conventional search/RAG pipeline can find a plausible old rate, mix different account tiers, or quote a calculator instead of the official product page. The system needs to explain why a fact is applicable, not simply find a similar paragraph.

## Walk through one answer

For a question about a 60-month auto loan on a particular model year:

1. `answer()` determines the requested observation date.
2. `select()` chooses a whole snapshot with no later data.
3. `rate_answer()` selects the auto-loan domain and the requested term.
4. The vehicle's year must fall inside the row's model-year range.
5. Official product tables outrank calculator duplicates.
6. Equal-authority disagreement causes an honest refusal.
7. The response uses the selected value, labels it APR, and returns the exact source row and snapshot ID.

For a historical certificate question, the same flow uses the earlier snapshot and keeps jumbo/regular, term, dividend rate, and APY distinct.

## Important code entry points

| Function | Purpose |
|---|---|
| `extract_rows` | Turn source tables and selected card prose into qualified facts |
| `ingest` | Store independent snapshots and build paragraph indexes |
| `select` | Prevent future-snapshot leakage |
| `rate_answer` | Match qualifiers, rank authority, handle disagreements |
| `factual_answer` | Apply evidence constraints to common non-rate intents |
| `retrieve` | Retrieve a paragraph for remaining questions |
| `conflicts` | Compare equivalent table facts, with evidence and resolution |

## Questions to prepare for

**Why no vector database?** The provided corpus is small, table qualifiers matter heavily, and a deterministic baseline is fast and auditable. Semantic retrieval could improve recall, but would not solve temporal filtering or authority resolution by itself.

**Why no LangGraph or agents?** The required workflow is a short deterministic pipeline. Additional orchestration is useful only if it improves extraction, verification, or debugging enough to justify its complexity.

**What does “current” mean?** The latest supplied snapshot. The application does not claim to know the live site after that capture.

**Is a newer crawl always more authoritative?** No. A newly crawled calculator can contain an older rate. Snapshot date controls what was observable; source type and explicit effective dates help decide which observed claim to trust.

**Why not call rate and APY a conflict?** They measure different things. A conflict requires the same product, tier, term, and metric.

**How do you know it is not memorizing?** Values are parsed from input evidence. Synthetic tests change the rates and dates and verify the answer changes. However, rules were developed on this corpus, so held-out evaluation is still essential.

**How strong is the score?** It is an observed public development-set result, not a hidden score. Conflict recall is unmeasured without the gold file, and public paraphrase checks are weak. Explain this openly.

**What would you improve first?** Generalized prose facts with validity intervals, better source-authority metadata, stricter unknown-product handling, and independent paraphrase/adversarial tests.

## Suggested local review

Run the tests, inspect a current auto answer, inspect a May certificate answer, and examine a few entries from `--conflicts`. Change one synthetic rate and rerun its test. Read the limitations in `NOTES.md`, then decide which improvements you can implement and confidently explain before publishing.
