# Orbital engineering workflow acceptance

October 17, 2026. Delivered build **bbf0bd7e9210** at http://127.0.0.1:8768/. This records the bounded orbital workflow increment, not full-product completion or flight validation.

## What works

The `orbital_trajectory` adapter binds ten scalar SI inputs and retains the existing solver's exact saved trajectory in the canonical project review. Five sampled/final-state metrics can be compared with declared requirements. The reference template contains four orbital criteria and an explicitly independent thermal case. Draft editing, impact preview, revision save, targeted recalculation/reuse, reports, history, playback, comparison and scoped investigations share these records.

Project playback is a derived view of an immutable canonical run, with its exact review identity and original model execution origin. Independent exploratory scenarios retain their own workflow and cannot change canonical requirement verdicts. See [ORBITAL_WORKFLOW.md](ORBITAL_WORKFLOW.md).

## Verification

- Full suite: **469 tests passed**, `python -m unittest discover -s tests`, in 104.361 seconds. Local HTTP tests used isolated temporary databases and loopback servers. Output is retained in ignored `work/orbit-workflow-tests.log`.
- New core tests cover independent analytic reference behavior, invalid bounds/units/bindings, sample-to-metric consistency, source identity, older three-source review compatibility, and limit-only/orbital-input/unrelated-input changes.
- Bridge tests verify canonical artifacts without recomputation, immutable history, same-revision older reviews, stale sources, invalid-input gaps, mixed exploratory/project comparison, export and identity checks.
- Four offline Assistant tests preserve complete saved/rechecked evidence, verify the deliberately compact provider projection and actual witness samples, block unreviewed revisions, and retain invalid-input gaps. Existing Assistant and explanation tests remain passing. These are offline protocol/evidence tests; no new live provider performance is claimed.
- Both modified JavaScript files passed Node syntax checks. A read-only integration review found no material blockers.

The full suite caught a regression in the older command-line demo: it iterated every reference template and attempted to compare the new, independent orbital project as a revision of the original component project. The demo now explicitly retains its original three-revision chain; the orbital template remains available. Its focused regression and the final full suite passed.

## Browser acceptance

`work/orbit-workflow-acceptance.json` records ten actual workflow check groups on an isolated server. They exercise template staging/creation, one canonical calculation, exact playback sample values, export, scoped Assistant navigation without inference, limit-only reuse with a new failed criterion, preserved historical limits, compatible overlays, orbital-only recalculation, unrelated thermal-only recalculation, draft blocking, exploratory independence, invalid-input abstention, reload and immutable original evidence.

Desktop and 390-pixel mobile screenshots were inspected; document overflow was absent. Requirement tables retain local horizontal scrolling on narrow screens. Native report PDF generation succeeded; extracted text contains sampled-scope qualifiers, findings and run identity. The first rendered page was inspected. Final cosmetic refinement remains deferred.

`work/orbit-workflow-guards.json` adds two actual history/selection checks and one explicitly injected delayed-response check. Running project checks from the generic Simulation entry selects the new canonical run. Selecting an older run of the same revision disables current-investigation navigation and labels it historical. A delayed project-history response cannot populate exploratory mode after a switch.

The ten-group workflow ran on build b6b8a96628cd. The final UI fix selects the new canonical run after an in-view rerun; the subsequent guard checks passed on delivery build bbf0bd7e9210. No physics or backend changes followed the passing full suite. Browser checks recorded no JavaScript errors, external requests or AI/investigation POSTs.

## Existing data and delivery

Before updating the server, the existing SQLite database was backed up under ignored `.local/backups/`. After restart and read-only browser inspection, all existing rows matched the backup exactly: one project, one revision, six canonical runs, two investigations, two model comparisons and one standalone simulation. SQLite integrity returned `ok`. Private provider/model configuration and the allowance ledger matched their previous file digests. Test projects and runs were confined to isolated databases.

The live app health check reports build bbf0bd7e9210 and `restart_required: false`. `work/live-orbit-workflow-smoke.json` verifies the visible build, orbital template staging and the user's preserved simulation with zero POSTs or browser errors. A backend restart clears any memory-only API key connection; local orbital engineering requires no key.

No paid model calls were made. Model selection and the existing cumulative allowance remain unchanged. No commit, push, deployment or publication was performed.

## Limits

Extrema assess stored samples over the specified duration; they are not continuous-time safety bounds. Final state criteria concern only the final recorded time. Numerical conservation diagnostics do not establish physical accuracy. Applicability, uncertainty, perturbations, thrust, atmosphere, attitude, GNC, launch/landing and coupled thermal/structural behavior remain outside this adapter. Historical receipts and unsigned digests do not establish authenticated approval or mission readiness.
