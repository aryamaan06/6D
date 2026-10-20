# Recalculation verification results — October 19, 2026

**PASS:** 1000 generated edit cases, seed `20261019`. 742 structurally valid revisions produced exactly equal complete engineering reviews through targeted and full recalculation. 258 structurally invalid edits were consistently rejected without saving a revision or result. Final discrepancies: zero.

This verifies software execution/reuse and evidence consistency against the same maintained calculators. Independent physical-model benchmarks and live AI evaluation remain separate work.

## Measured coverage

| Case family | Generated edits |
| --- | ---: |
| attitude_control | 125 |
| orbital_trajectory | 125 |
| radiative_equilibrium | 125 |
| drag_load | 125 |
| static_cantilever | 125 |
| ideal_propulsion | 125 |
| calculation_chains | 125 |
| power_energy_budget | 125 |

The run covered 64 named operation classes, including numerical/source/unit edits, input remapping, criteria/metadata changes, model addition/removal/reordering, unsupported models, malformed records, scalar link changes, changed upstream assumptions, multihop dependencies, fanout, gaps and no-op numeric representations. Operations cycle within stratified families; numeric choices are seeded. These are constructed finite software cases, not 1,000 independently sourced flight designs or uniform samples of all possible projects.

Observed model statuses: `{"completed": 2264, "invalid_inputs": 40, "not_assessed": 36}`. Observed requirement statuses: `{"met": 2925, "not_assessed": 184, "not_met": 321}`.

Models executed in edited revisions: **415**. Models reused: **1925**. A separate dependency audit checked all **1925** recorded reused models using its own traversal and exact rational input identities, without calling production reuse/impact helpers. No model with changed consumed inputs, upstream definitions or link rationales was incorrectly reused. Conservative extra calculations are allowed and not counted as incorrect engineering.

Four bounded multi-revision histories additionally compared **12** saved runs with full recomputation: repeated same-revision execution, change then revert, an unrun intervening revision, and source rewiring followed by a former-source edit and a new source gap. Historical stored rows and execution origins were checked.

## Defect found and fixed

A radiative-equilibrium case with zero supplied heat exposed an exact-evidence defect. Changing background temperature from `+0.0` to `-0.0` previously shared a reuse key, although the adapter could retain the IEEE zero sign in its result. Reused and fresh results had the same numerical magnitude but different serialized evidence fingerprints/review digests.

`workspace._model_key` now preserves negative zero while retaining ordinary equal integer/float equivalence. The original failing case is retained in `artifacts/recalculation-verification/signed-zero-before-fix.json`; a focused regression verifies exact full-review equality after the fix. No claimed physical mission outcome changes.

## Verification of the checker

A focused sensitivity test deliberately forces an unsafe constant reuse key. The checker rejects its stale thermal calculation against the full reference. Other tests verify comparison of assumptions, consistent rejection without writes, wrong-unit gaps, seed reproducibility, signed-zero handling and independent detection of same-value/new-source and upstream-rationale changes.

The full regression suite passed **754 tests** in 258.478 seconds. A final focused run passed **16 verification/history tests**, including three additional dependency-audit tests introduced after full-suite discovery. Counts overlap and should not be added together. Full log: `work/verification-final-tests.log`.

## Receipts and reproduction

Main receipt: `artifacts/recalculation-verification/seed-20261019-cases-1000/summary.json`.

- Summary digest: `235d90f5fd720b5b837dff082edc647a3a1968c53981b9dfb949fe6ae65332bf`.
- Case ledger SHA-256: `a9c91752ff58f1befe88acd7ba1bbc4d9adbdc8f7697b2b89ad8be2ded444e62`.
- Every case ledger row records identity, family, operation, before/after digests, outcome, findings/statuses and execution/reuse IDs.
- Summary records source fingerprints and Python version. All JSON input fixtures, including legacy `design-baseline.json`, have additional fingerprints in `fixture-manifest.json`.
- Separate audit receipt: `reuse-audit.json`, including its checker source fingerprint and reference to the main receipt.
- Benchmark elapsed time: 403.689 seconds (including full verification/persistence overhead; not an application latency benchmark).

From the repository folder, with the repository's Python runtime:

```powershell
python tools/verify_recalculation.py --seed 20261019 --cases 1000 --output artifacts/recalculation-verification/reproduction
python tools/audit_recalculation_reuse.py artifacts/recalculation-verification/reproduction
```

No credentials, network or paid model calls are required. All benchmark workspaces are temporary and isolated. Founder records, provider selection and spending configuration are audited separately in `work/verification-preservation.json`.

## Product delivery and limits

Local application: http://127.0.0.1:8768/. Build **e1e69fe17796**, runtime `ecd176ee7823ac2f3278e0c1734e472b24c6b9bd59f4a760687ab41f2331443c`. This milestone adds verification tooling/reporting and the bounded reuse fix; the workspace interface is unchanged.

Finite seeded coverage does not prove all configurations, numerical extremes, concurrent requests, integration tools or physical assumptions. Short fixed orbital/control grids keep this software benchmark bounded; it is not the promised independent long-duration orbit or controller reference study. No expanded physics, live AI grading, customer validation, public deployment or launch-readiness assurance was performed. Paid Nebius calls: **zero**.
