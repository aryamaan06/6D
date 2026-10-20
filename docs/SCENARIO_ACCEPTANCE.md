# Scenario study acceptance

Delivered October 18, 2026, Asia/Calcutta, at http://127.0.0.1:8768/. Verified build **1ee19b0f7496**, runtime `084707a531da578792dffd376b5a93bac8a521ccfbfdc853f65dda7ecc859b49`, with `restart_required: false`.

## Implemented

Explicit single-input sweeps and named multi-input alternatives use the five existing maintained model types. Each immutable study binds a current saved baseline and preserves project revision/canonical findings. Results include per-case criteria and margins, result changes, distinct met/not-met/not-assessed states, saved-value plots, actual calculation/reuse provenance, case explanations and next checks, scope disclosures, history, JSON export and printable reports. See SCENARIO_STUDIES.md for instructions and bounds.

The feature does not add uncertainty probabilities, optimization, interpolated safe ranges, implicit subsystem coupling, new rocket physics, scenario playback controls or automatic promotion to a project revision.

## Automated verification

The full repository suite passed **504 tests** in **81.237 seconds**, using `python -m unittest discover -s tests -q`. Output is retained in ignored `work/scenarios-regression.log`. JavaScript syntax checks passed.

Sixteen focused scenario tests cover independent thermal and quadratic drag references; <=, >= and exact-target margin semantics; finite-difference overflow; named multi-input dependency scope; limit-only reuse; invalid physical inputs becoming unassessed; immutable baseline records; strict request bounds and malformed values; required baseline and locking; source changes before/during execution; orbital sample/work budgets and actual retained trajectories; immutable/history/source freshness; reopened no-calculation reads; and rehashed internally inconsistent record rejection. Two new real HTTP tests cover intake, baseline gating, export, unchanged workspace records, static asset availability and cross-origin/extra-field rejection. Existing physics, provider-budget, investigation, authoring, simulation and storage tests remain included.

## Browser and report verification

Fourteen scenario browser groups passed in an isolated database with no usable credential and a provider factory that refuses inference:

- Eight workflow groups (`work/scenarios-browser-acceptance.json`): no fabricated defaults; thermal reference sweep; criterion-only reuse; invalid emissivity abstention; explicit multi-input alternatives; persisted history and exact export; native PDF/desktop/mobile layouts; and draft blocking.
- Four history/control groups (`work/scenarios-browser-guards.json`): incomplete CSV values preserve the selected report with no calculation; replaced baseline labels history and blocks stale context; unreviewed later revisions inspect old evidence without a false current result; and explicit baseline checks restore study readiness.
- Two view guards (`work/scenarios-view-guards.json`): stale context offers a working reload action, and delayed study completion cannot overwrite a different selected project's workspace.

The existing project-authoring walkthrough passed all **nine** groups, and the orbital engineering/playback walkthrough passed all **ten** groups on this build. No JavaScript errors, external requests or paid-model endpoints were observed. All mutation/calculation checks used temporary isolated workspaces. An initial browser test failed because its edit-button selector matched two existing controls; that test selector was corrected, and the complete workflow passed.

Desktop and 390-pixel screenshots were inspected. Print export contains 14 nonempty pages for the three-case full evidence report; its study identity, baseline run/review, every case review and exact thermal results were checked against the saved receipt (`work/scenario-pdf-verification.json`). Full receipt JSON contains source inputs and orbital samples where applicable. Styling remains provisional, consistent with the current product direction.

## Live data and delivery

Before the increment, the founder database was backed up through SQLite under `.local/backups/`. After the backend restart, all existing rows match that backup exactly: **one project, one revision, six runs, two investigations, two model comparisons and one standalone simulation**. SQLite integrity is `ok`. The new `scenario_studies` table exists with zero test records in founder storage. Private provider/model configuration and the cumulative allowance ledger retain their previous file hashes (`work/scenarios-migration.json`).

Read-only live browser verification confirms the visible build, Scenarios forms/history and existing Simulation page (`work/live-scenarios-smoke.json`); every POST was blocked. The founder's saved revision currently requires baseline checks because its recorded verification sources predate the current maintained sources. That historical evidence was preserved. **Scenarios → Run baseline checks** explicitly creates a current baseline before a new study; merely opening the page does not calculate it.

The backend was restarted and health-checked at the normal address. Restart clears the memory-only Nebius connection; local studies require no key. **No paid inference, provider selection change, allowance change, commit, push, publication or deployment occurred.**
