# Validation index — counts are scoped, not additive

Updated October 24, 2026. A software test checks particular behavior. Same-calculator consistency, analytic references, separate-tool numerical comparisons, live model behavior and human/user validation are different kinds of evidence.

## Current review run

A full offline discovery on Python3.14.7 executed **1,225 test methods** in approximately 699 seconds, with external socket connections blocked and no paid inference. Initial outcome: **two failing methods, one cleanup error associated with one of those methods, and one skip**. Application/test source hashes stayed unchanged during the run.

The failures were:

1. Authoring API fixture expected seven model types, omitting the already implemented powered-flight model. The expected explicit set now includes all eight.
2. Offline Ultra diagnostic fixture exhausted its15second wait while a worker was still running, then attempted to delete its open SQLite directory. The isolated six-test module passed before modification. The fixture now allows a bounded 45 second wait, polls less aggressively, and waits for session ownership to finish before removing SQLite files. This is not a provider retry or weakened model acceptance.

After these test-fixture changes, the two affected modules passed **11 tests**, no failures/errors/skips. No application source, numerical criteria, model selection or paid provider setting changed. The one full-run skip was the development-only SciPy reference. Its first standalone attempt also skipped without the dependency path; a subsequent cached development environment (Python3.12.14/SciPy1.18.1) passed that one method covering four constructed DOP853 comparisons. No dependency was installed into the application. The full suite was not repeated after these fixture-only corrections. Its initial failing output is preserved rather than represented as a green full run.

Logs/summaries: `work/claude-part2-review/02-full-test-output.txt`, `test-summary.json`, `02b-corrected-tests.txt`, `correction-summary.json` and `09-test-fixture-corrections.diff.txt`. These are included in the local Claude packet. Full test output is not itself independent engineering validation.

## Earlier checkpoints

| Evidence | Date/scope | Interpretation |
| --- | --- | --- |
| 754-test full regression | October 19 recalculation-verification snapshot | Older source snapshot; its follow-up16-test history audit overlaps and is not added. |
| 765-test full regression | October 19 reference-benchmark snapshot | Older source snapshot, not current total. |
| 247 distinct affected tests | October 24 AI/source/guard/overview work | Targeted affected modules, not a full-discovery count. |
| 22 Tavily service/API tests | October 24 follow-up | Repeated subset already represented in the broader targeted checks; not247+22. |
| 1,000 generated edit cases | October 19 reuse checker | 742 valid revisions equal full recomputation,258 invalid rejected; constructed edits, not1,000 flight designs. Predates powered flight. |
| 30 published-reference/domain checks | October 19 seven-model pack | Source-classified numeric/domain cases; not30 independent missions. |
| Eight orbital external-reference cases | October 23 accuracy work | Constructed two-body comparisons with NASA CSPICE, not flight truth or a universal error bound. |
| Current four-case live Super qualification | October 24 |16 accepted responses; bounded cases and settings, not general semantic accuracy. |
| Browser groups/assertions | Each feature's dated results | Interaction checks; they are not extra Python test methods or physical-model benchmarks. |

Older741-style figures may remain in dated historical notes. They are not current totals. No historical count is silently edited into a new one. Independent human engineering review, customer validation and real flight-data validation remain unestablished.
