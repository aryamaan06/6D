> October 25 final audit: [1419-method discovery](FINAL_BUILD_AUDIT.md) recorded 1,413 passes, five skips, no assertion failures and one Windows socket error. The unchanged affected module passed 7 methods; the exact method passed 20 more repetitions. The original full run is not green. Browser navigation and reference-source matching also passed. [Machine-readable result](validation/FINAL_BUILD_AUDIT.json). No paid calls or application source changes.

> Build F preparation, October 25: [results](BUILD_F_RESULTS.md) and [scoped checks](validation/BUILD_F_CHECKS.json) cover 106 distinct affected methods (105 passed, one Windows Docker-unavailable skip), nine integrated browser groups and exact owner-data preservation. Final 58 affected methods passed after UTF-8/source correction. [Linux/container CI](https://github.com/aryamaan06/6D/actions/runs/40161774801) passed: scoped Linux checks and actual constrained container login/restart/sign-out succeeded. Public TLS/deployment and current-build live AI remain unverified. Counts overlap previous suites and are not a full-suite total.

> Build E, October 25: [results](BUILD_E_RESULTS.md) and [96-method scoped regression summary](validation/BUILD_E_CHECKS.json). 95 passed, one Windows symlink-privilege skip; native DPAPI and mocked linked-path guards passed. Eight integrated browser groups and read-only actual delivery checks passed; no paid/provider calls. This is affected verification, not a new full-suite total.

> October 25 corrections: [delivery scope](CORRECTIVE_BUILD_RESULTS.md), [machine-readable checks](validation/CORRECTIVE_BUILD_CHECKS.json), [paired timing report](HISTORY_PERFORMANCE_RESULTS.json) and [20 separate reference cases](validation/CANONICAL_SOURCE_REFERENCE_RESULTS.json). Full discovery ran 1,338 methods with three stale assertion failures and three SciPy skips; the corrected three modules passed 37 methods. Earlier results remain below as dated history; counts overlap.

> Build D, October 24: [scoped results](BUILD_D_RESULTS.md) and [machine-readable history](validation/BUILD_D_CHECKS.json) add 98 distinct relevant methods across seven modules, six browser groups and bounded live whole-project records. Counts overlap earlier modules and are not additive to past suites. One final current-source changed-rocket case completed; historical generic/failed replies remain distinct.

# Validation index — counts are scoped, not additive

Updated October 24, 2026. A software test checks particular behavior. Same-calculator consistency, analytic references, separate-tool numerical comparisons, live model behavior and human/user validation are different kinds of evidence.

## Current review run

A full offline discovery on Python3.14.7 executed **1,225 test methods** in approximately 699 seconds, with external socket connections blocked and no paid inference. Initial outcome: **two failing methods, one cleanup error associated with one of those methods, and one skip**. Application/test source hashes stayed unchanged during the run.

The failures were:

1. Authoring API fixture expected seven model types, omitting the already implemented powered-flight model. The expected explicit set now includes all eight.
2. Offline Ultra diagnostic fixture exhausted its15second wait while a worker was still running, then attempted to delete its open SQLite directory. The isolated six-test module passed before modification. The fixture now allows a bounded 45 second wait, polls less aggressively, and waits for session ownership to finish before removing SQLite files. This is not a provider retry or weakened model acceptance.

After these test-fixture changes, the two affected modules passed **11 tests**, no failures/errors/skips. No application source, numerical criteria, model selection or paid provider setting changed. The one full-run skip was the development-only SciPy reference. Its first standalone attempt also skipped without the dependency path; a subsequent cached development environment (Python3.12.14/SciPy1.18.1) passed that one method covering four constructed DOP853 comparisons. No dependency was installed into the application. The full suite was not repeated after these fixture-only corrections. Its initial failing output is preserved rather than represented as a green full run.

Logs/summaries: `work/claude-part2-review/02-full-test-output.txt`, `test-summary.json`, `02b-corrected-tests.txt`, `correction-summary.json` and `09-test-fixture-corrections.diff.txt`. These are included in the local Claude packet. Full test output is not itself independent engineering validation.

## Build B affected verification

The guided-ascent regression ran 293 methods: 292 passed; one catalog-count fixture needed eight changed to nine. Its corrected 12-method authoring module passed. These runs cover 293 distinct passing methods, not 305. Four separately integrated DOP853 cases also passed, including the interactive reference grid. This is not a full-suite count. See [BUILD_B_RESULTS.md](BUILD_B_RESULTS.md) for logs, browser evidence and scope.

## Earlier checkpoints

Build C covers **320 distinct affected Python methods** across the solver (14), adapter/contracts (84) and remaining regressions (222). One initial authoring-fixture expectation of catalog fields was corrected and its 12-method module passed; overlaps are not added. Four separate staged DOP853 cases and eight actual-solver browser groups passed. See [BUILD_C_RESULTS.md](BUILD_C_RESULTS.md) for boundaries and preserved initial/follow-up results. This remains targeted verification, not a new full-suite total.

Build A's integrated rocket reference passed **55 affected Python tests**, including 14 new reference/profile/API methods and 41 existing regressions. Targeted and full recomputation matched for the constructed thrust reduction and restoration. This targeted result is separate from the earlier 1,225-method full discovery. Browser acceptance and the exact constructed scope are recorded in [BUILD_A_RESULTS.md](BUILD_A_RESULTS.md).

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

## October 25 UI navigation/font scope

[Delivery](WORKSPACE_NAVIGATION_RESULTS.md): 77 scoped Python methods (76 passed, one hosted Docker-environment skip), six Node history contracts and isolated browser acceptance. These overlap existing suites and are not a new full discovery total. Navigation tests use constructed projects and forbidden external transports. No live AI qualification is established by these checks.

## October 25 Build 2 model choice/readability

[167 combined offline methods passed](THREE_MODEL_RESULTS.md), plus6 Node history contracts,8 model browser groups and17 navigation groups. Three live phases attempted13 jobs:10 completed,3 failed,56 request reservations and USD0.92674272 conservatively reserved. The failures remain recorded; successful cases span source corrections, not one all-model final-source qualification. Counts overlap prior suites; no full discovery or independent human validation is claimed. [Machine summary](validation/THREE_MODEL_CHECKS.json).
