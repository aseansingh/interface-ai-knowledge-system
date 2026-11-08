# Conflict-review update

- Separate personal and business deposit/card facts in their comparison keys.
- Recognize both `/business/...` and `/business-rates` route forms.
- Use the same audience classification for rate-question filtering; business-only evidence cannot answer a personal savings question.
- Do not infer personal audience for unlabeled general rates pages. Omit unidentified-audience deposit/card rows from conflict reports until identity can be established.
- Name the selected and competing source URLs in conflict explanations. State source authority or actual effective-date priority as appropriate; keep equal-priority disagreement unresolved.
- Include parsed effective-date evidence with cited rows and exclude future-effective claims from current conflict comparison.
- Explicitly label historical conflicts, while retaining the required list-of-Conflict contract.
- Add nine regression tests; all 25 tests pass. The unmodified public evaluator remains at 0.9364, with zero runtime errors and zero stale-trap hits. Hidden evaluation and gold conflict scoring remain unavailable.

## Updating an existing local copy

Extract the updated ZIP separately. Copy the contents of its `knowledge-system` folder into your existing solution folder, replacing same-named files. This updates the code, tests, notes and aggregate validation report together. Do not replace or move the separate participant-kit folder. Rerun the tests and the organizer evaluator before publishing.
