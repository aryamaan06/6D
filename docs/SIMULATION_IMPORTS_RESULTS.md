# Simulation imports delivery evidence

October 23, 2026 · build `3eed1f8127d9` · http://127.0.0.1:8768/

## Delivered scope

Explicit UTF-8 time-history CSV intake, units/frame/configuration declarations,
bounded validation, exact-sample playback and position projections, supported
baseline comparisons, frozen append-only history and report/JSON integration.
No physical solver or canonical engineering verdict is changed by importing.
See [guide](SIMULATION_IMPORTS.md) and [acceptance](SIMULATION_IMPORTS_ACCEPTANCE.md).

## Verification

- **15 backend acceptance groups passed**, including strict parser and size/row/
  column/channel bounds, units/frame/time checks, exact and partial alignment,
  numerical gaps, ambiguous cutoff values, stale context, tampering and history
  reads with the orbital solver blocked. A fixture-only baseline expectation was
  corrected and its group rerun; display-only stale flags do not enter canonical
  run receipts.
- **Six HTTP acceptance tests passed**: preview/save/reopen/export, combined
  snapshot equality, real bound comparison, frame mismatch, stale baseline,
  malformed/cross-origin rejection, static assets and a CSV larger than the old
  general request bound. These used isolated databases and forbidden providers.
- **108 existing integration regressions passed**, zero failures/errors/skips:
  scalar test data and HTTP paths, linked evidence and reports, simulation bridge,
  lifecycle and coverage HTTP paths. Module names/results are retained locally in
  `work/series-regression.json`.
- **Seven real browser workflow groups passed**: explicit synthetic import,
  playback/scrub, actual CRLF file upload and three-channel mapping, exact bound
  comparison, position projection, original CSV/review preservation, full report
  and combined JSON, navigation/reload history. Some checks share a group. No
  browser errors, external requests or paid calls occurred. The screenshot was
  visually inspected. Browser testing found and corrected a collapsed editor
  when starting another import; the full workflow passed after correction.
- Node syntax and Git whitespace checks passed. A separate coding-agent review
  identified the need for explicit read transactions; that fix is included.
  Agent review is not independent human aerospace validation.

Run `python -m unittest discover -s tests -p test_workspace_series.py` and
`python -m unittest discover -s tests -p test_simulation_imports_api.py` for the
new backend/HTTP checks. No external reference package is needed for import
arithmetic. Comparing copied canonical samples is an alignment test, not an
independent physical validation.

## Preservation and controls

Test imports were saved only to disposable projects/databases. All pre-existing
founder workspace/budget rows and provider/Assistant configuration hashes match
the prior baseline, including thirteen runs and two investigations. Startup adds
an empty `simulation_imports` table; it does not seed example imports or rerun
calculations. Final delivered-app checks are recorded locally in
`work/series-current-results.json`.

No paid calls, model activation, provider connection, GitHub push or deployment
occurred. The existing USD29.50 ceiling and USD2.30350988 reservations are
unchanged; reservations are not billed usage. Further engineering/AI milestones
remain separately authorized work within the agreed submission scope.
