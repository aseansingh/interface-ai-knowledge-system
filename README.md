# Temporal credit-union knowledge system

An offline Python implementation of the interface.ai build-assignment contract. It answers from dated website snapshots, selects qualified rate-table facts, cites evidence, and abstains when a matching fact is unavailable or unresolved.

**Status: tested first implementation for review, not yet a final submission.** The public benchmark is a development set, not evidence of hidden-test performance. Read `NOTES.md` for limitations and `WALKTHROUGH.md` before presenting this work.

## Update: conflict identity and explanations

The updated version separates business and personal deposit/card facts, including legacy `/business-rates` URLs. Unspecified audiences are not silently treated as personal. Conflict reasons name the competing sources and explain whether source authority or an actual effective date decided the winner. Historical entries are explicitly labelled. See `CHANGELOG.md`.

## Files

- `submission/solution.py`: `build()`, `ingest(snapshot)`, `answer(question, as_of=None)`, `conflicts()`.
- `tests/`: 25 synthetic temporal, tier, audience identity, authority, and abstention tests.
- `tools/evaluate.py`: runs the organizer's unmodified scorer.
- `tools/ask.py`: inspects cited answers and conflicts.
- `validation/public_report.json`: aggregate public evaluation results, without website content.
- `requirements.txt`: standard library only; Python 3.11 or newer. No API keys.

## Run locally (Windows PowerShell, macOS, or Linux)

1. Extract this project ZIP.
2. Separately extract the original participant ZIP. Keep that folder **outside** this repository. Do not extract its five inner snapshot ZIPs yourself; the supplied scorer handles those.
3. Open a terminal inside this project's `knowledge-system` folder.
4. Run the commands below. Replace `C:/path/to/hackathon-knowledge-kit-participant` with the folder containing the supplied `harness`, `eval`, and `snapshots_zip` folders.

```sh
python --version
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/evaluate.py --kit "C:/path/to/hackathon-knowledge-kit-participant"
```

The evaluator writes `results/report.json` and `results/per_question.jsonl`. Results are ignored by Git because they can contain source text.

For the organizer's exact command, run from the original kit folder:

```sh
python harness/run_eval.py --submission "C:/path/to/knowledge-system/submission" --eval eval/public_eval.jsonl
```

## Inspect the evidence

```sh
python tools/ask.py --kit "C:/path/to/hackathon-knowledge-kit-participant" --question "What's the APR for a 60-month auto loan on a 2025 vehicle?"
python tools/ask.py --kit "C:/path/to/hackathon-knowledge-kit-participant" --question "10-month jumbo certificate APY" --as-of 2026-05-31
python tools/ask.py --kit "C:/path/to/hackathon-knowledge-kit-participant" --conflicts
```

Every answer exposes `text`, `sources` (URL, snapshot ID, excerpt), `confident`, and `conflict_note`. All content comes from the local kit. There are no live website calls.

## Measured public performance

See `validation/public_report.json` for the exact run:

| Measurement | Result |
|---|---:|
| Supplied starter weighted QA score | 0.0930 |
| This version weighted QA score | 0.9364 |
| Public questions | 40 |
| Stale-trap hits | 0 |
| Runtime errors | 0 |
| p95 answer latency | 0.14 seconds |
| Ingestion | 5.2 seconds |

Latency depends on hardware. The public run does **not** grade conflict detection because the organizers' gold conflict file is not provided. Its paraphrase groups each have only one public question, so the reported perfect consistency score mostly demonstrates repeatability; it does not establish broad paraphrase robustness.

## Before publishing

The project package deliberately excludes the supplied kit, snapshots, PDF, per-question results, extracted indexes, and keys. Keep them outside the repository. `.gitignore` is an additional precaution, not a substitute for reviewing staged files.

After reviewing and understanding the implementation:

```sh
git init
git add .gitignore README.md NOTES.md WALKTHROUGH.md requirements.txt submission tests tools validation
git diff --cached --stat
git diff --cached
git commit -m "Implement temporal evidence-based knowledge system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
git rev-parse HEAD
```

Create an empty public GitHub repository before adding the remote. Email the repository URL and the full commit SHA to the assignment address when you are satisfied with the work. No repository has been created or email sent by this project.
