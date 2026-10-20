# Test-data comparison acceptance

Delivered October 18, 2026, Asia/Calcutta, at http://127.0.0.1:8768/. Live build **acc50e0ee10b**, runtime `b7051df1eec77ad06fef6d7f513686d36eaad67afd81d7670097aa98005809ec`, with `restart_required: false`.

## Delivered scope

Test data is a connected workspace view supporting UTF-8 CSV upload/paste, explicit column mapping, raw/normalized previews and row quality gaps, declared source/data origin/observable/conditions, immutable exact-baseline comparisons, two separate row findings, scalar plots, history, JSON export and print/PDF. The original submitted CSV and SHA-256 are retained. The comparison performs arithmetic on recorded evidence; saving or reading it executes neither physics nor inference. Existing project findings remain unchanged.

The two outcomes are measured requirement satisfaction and agreement with a prediction within an explicitly supplied absolute tolerance. They can disagree. Same-observable/aggregation/condition matching is an unverified user declaration, not a physical applicability assessment. Missing information stays unassessed. Supported-model coverage, uncertainty, test authenticity/calibration, time-series alignment, qualification, automatic calibration and general physical validation remain outside this increment. See TEST_DATA_COMPARISON.md for the procedure and boundaries.

## Automated verification

The full repository suite passed **534 tests** in **111.665 seconds**, using `python -m unittest discover -s tests -q`. Output is retained in ignored `work/test-data-regression.log`. Final JavaScript syntax checks passed.

Twenty-five focused backend tests include:

- Independent drag arithmetic and separate requirement/agreement outcomes, including measurement failure with agreement, exact boundary inclusion, `>=`, exact `==`, explicit zero tolerance and finite difference overflow.
- Missing/negative/invalid tolerances, wrong units, missing/different/unknown conditions, unknown/unsupported requirements, duplicated IDs, invalid values and preservation of quality gaps.
- Strict CSV size/shape/header/mapping bounds, quoted cells, UTF-8 BOM, original submitted hash, no inferred defaults and untrusted formula text remaining inert.
- Unsupported integer precision becoming a gap instead of a rounded comparison; unsafe baseline operands are omitted from usable comparison records. Binary floating-point semantics are explicit.
- Immutable baseline records, no solver/provider on save/read, reopened history, revision/source/baseline freshness, concurrent-save/source/baseline-change guards and internally inconsistent rehashed record rejection, including boolean/number substitutions.

Five additional real HTTP tests check the same separation using an independently specified 300 N drag reference, exact export/read/list, no canonical mutation or solver execution, quoted multiline preview, missing tolerance, condition/unit gaps, required baseline and local-origin/strict-body/static-asset boundaries. Existing physics, provider-budget, authoring, scenario, simulation and investigation tests remain in the full suite.

## Browser and reports

Eleven new browser acceptance groups passed in isolated temporary workspaces with a provider factory that refuses inference:

- Eight end-to-end groups (`work/test-data-browser.json`): explicit empty intake; exact UTF-8 BOM + Windows CRLF preservation through file upload, mapping and metadata changes; independent arithmetic and separate findings; compatible per-row plots; JSON/PDF/mobile layout; saved history with no read-time calculation; inert hostile labels/formulas with unknown-condition gaps; draft/unreviewed revision guards and historical binding.
- Two view guards (`work/test-data-view-guards.json`): reloading a replaced baseline preserves unsaved CSV/mappings/metadata/preview, and delayed completion cannot overwrite a different selected project.
- One precision guard (`work/test-data-precision-browser.json`): unsafe CSV integers and a precisely encoded unsafe baseline criterion are visibly unassessed, produce no misleading plot and disclose browser preview precision limits.

Existing scenario comparison also passed eight browser groups, and orbital engineering/playback passed ten. No JavaScript errors, external requests or paid-model endpoints were observed. All calculations and saved acceptance records used isolated data.

An initial browser fixture accidentally doubled Windows CRLF line endings into CRCRLF. The parser correctly rejected those ragged rows; the harness encoding was corrected, then the full workflow passed. Product review also caught real CRLF textarea-normalization and large-integer display hazards; both were fixed before acceptance. Original file text is retained in memory until an actual CSV edit, and unsupported integer comparison operands are explicit gaps.

Desktop and 390-pixel layouts were visually inspected. The complete constructed report exports to **11 nonempty PDF pages**. Its comparison identity, original CSV hash, baseline run/review identities, every supplied measurement, separate outcomes and synthetic/unverified declarations were checked against the exported receipt (`work/test-data-pdf-verification.json`). Existing provisional styling is retained.

## Saved data and live delivery

The founder database was backed up through SQLite under ignored `.local/backups/` before implementation. After restarting the backend and read-only live inspection, every previous row matches that backup exactly: one project, one revision, six canonical runs, two investigations, two model comparisons, one standalone simulation and zero scenario studies. The new `test_comparisons` table contains zero acceptance records in founder storage. SQLite integrity is `ok`. Provider/model configuration and the cumulative allowance ledger retain their previous file hashes (`work/test-data-migration.json`).

The live browser check (`work/live-test-data-smoke.json`) blocked every POST and verified the visible delivered build, empty explicit Test data forms, Scenarios and Simulation, without changing the workspace. The founder's historical canonical evidence still needs explicit baseline checks before a new comparison; the application offers that action. No historical evidence was overwritten or recalculated automatically.

No paid requests, provider selection change, allowance change, commit, push, publication or deployment occurred. Restart clears the memory-only Nebius connection; this feature works without a key. Optional independently specified synthetic walkthrough files are supplied under `examples/` and clearly labelled as constructed, not physical test data.
