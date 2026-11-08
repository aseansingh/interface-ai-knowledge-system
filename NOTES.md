# Approach and limitations

## Evidence and time

The system stores each full snapshot independently. `as_of` selects the latest snapshot on or before the requested day; no date selects the newest supplied snapshot, not the computer's wall-clock date. Pages missing from a later full snapshot are not silently carried forward. Invalid dates and dates preceding the first snapshot cause abstention. Explicit ISO dates and month/year expressions following “as of” are also recognized. Dates later than the final snapshot use the latest available observation; this does not claim the live website is unchanged.

Markdown rate tables become rows with product, term, model-year range, balance/loan tier, metric labels, effective date when extractable, URL, snapshot ID, and original row evidence. APR, APY, and dividend rate remain separate. Personal card ranges can also be extracted from card-heading prose. Values are derived at ingestion, not loaded from the practice answer key. The code never reads `eval/` or expected answers. Product/intent extraction rules were developed against the supplied corpus and public practice questions and therefore can overfit its structure.

Within a selected snapshot, official product pages outrank calculators and editorial pages. Explicit table effective dates break ties among equally authoritative sources; future-effective rates are excluded from answers. Unresolved equally authoritative disagreements cause abstention. This is a documented heuristic, not a universal claim that product pages are always correct. Named product labels and qualifiers must match before competing values are compared. Deposit/card identity also includes a personal/business audience, inferred from explicit product or section labels and then from URL routes, including legacy hyphenated routes. An unspecified audience is not merged with a known audience. This inference is conservative but still heuristic: URL naming alone cannot prove account eligibility. Normal rate changes between separate full snapshots are not treated as simultaneous contradictions.

General information uses paragraph retrieval with token normalization, inverse-document-frequency weighting, source authority, and intent constraints. Routing numbers and branch addresses are selected from appropriate evidence fields. Historical announcement schedules are labelled as historical examples rather than asserted as current hours for every branch. Narrow evidence selectors support membership, closure notices, contact options, and student-loan summaries. There is no generative model or API dependency; determinism and low latency make this a useful auditable baseline.

## Conflict report

`conflicts()` compares same-snapshot table facts with the same product/tier and metric, normalizing numeric formatting. It includes competing values, supporting excerpts, and either a winner or an unresolved status. The reason names winning and competing URLs and identifies the rule actually used; a date is cited only when effective-date priority decides the comparison. Future-effective claims are excluded from current conflict comparison. Deposit/card rows with unspecified audience are omitted from conflict reporting, trading recall for reduced false positives. Across snapshots it retains the most recently observed contradiction for each key; the reason records that observation date and labels the entry historical when it predates the newest snapshot. Consequently a reported historical contradiction is not necessarily still present in the newest snapshot. It does not claim to enumerate all prose contradictions, expired promotions, fees, branch-count differences, or all inconsistencies within footnotes.

## Validation and interpretation

The organizer's scorer and evaluation files were not modified. The final aggregate public report is included. Synthetic tests cover changed input values, date cutoffs, future effective dates, deleted pages, term/model-year matching, APR/APY separation, source precedence, unresolved ties, equivalent terms, invalid dates, and repeatability. There are 25 tests, including nine regression tests for audience isolation, actual-rule explanations, unresolved ties, future dates, and historical reporting. These are additional behavioral checks, not a replacement for held-out evaluation.

Two public-score caveats matter. The all-certificate-rates question has no `must_include` tokens; without the optional LLM judge, the scorer gives zero even when a full sourced rate list is returned. The volunteer-time question expects a 2023 count while the selected snapshot also includes a newer article reporting 2024 participation; this implementation returns the newer article with the year stated, rather than embedding the expected older number. Relative dates such as “last year” still need more rigorous event-time handling. Some source-credit losses reflect citation URL preferences rather than wrong numeric values.

## Known limits and next work

- Deterministic query parsing handles common qualifiers, not unrestricted natural language. Unknown product names, compound conditions, missing currency signs, or ambiguous phrasing can retrieve incomplete or irrelevant evidence. Confidence is heuristic, not calibrated.
- Generic financial descriptions and fee tables are not comprehensively normalized. Non-table facts use retrieval rather than a full temporal fact model.
- Effective-date extraction supports one common date format and nearby text. It does not model validity intervals, promotion expiry, all scheduled changes, or retroactive corrections comprehensively.
- Source authority is URL-based. Contradictions where two official pages have different publication/validity semantics need a richer policy. Conflict precision/recall against organizer gold is unknown.
- Matching is not multilingual; abbreviated product names and novel paraphrases need held-out tests. The public set was used during development and is not an unbiased test set.
- The full website history is kept in memory. This is suitable for this kit, not a production-scale persistence strategy.
- Input text is never executed and no model consumes page instructions. A future LLM extractor should treat all website content as untrusted data, enforce structured schemas, validate quotes, and keep deterministic time/authority checks outside the model.

Before final submission, improve prose claim extraction and event-time semantics, add a held-out paraphrase set and adversarial unknown-product tests, inspect sampled conflicts manually, and have the candidate run and explain the implementation locally. An optional schema-constrained LLM extractor could broaden coverage, but should not replace evidence validation or require untested API credentials in the submitted default path.

## Dependencies and AI assistance

Python 3.11+, standard library only; no API keys, external services, embeddings, or network calls. AI assistance was used to inspect the kit, implement this first version, write tests, and review public failures. The candidate should review and own every design decision before submission.
