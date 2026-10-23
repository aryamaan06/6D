# Engineering coverage delivery

Delivered October 21, 2026. Local build **202b570103de**, opening at **http://127.0.0.1:8768/** with the independent project Python runtime.

## Delivered

- Sidebar Engineering coverage workspace: phase groups, discipline/state filters, existing requirement cards, explicit new checks, rationale and next-step editing.
- Separate applicability declaration, model-fit declaration, calculation status and original requirement result. Unknown applicability does not become established because a criterion passes.
- Append-only declarations, displayed-context/base-version conflict guards, relevant dependency review flags and conservative project-wide flags for unmapped checks. Earlier revisions and project drafts are read-only.
- Current model assumptions/exclusions and saved declaration histories, with navigation back to a linked requirement.
- Coverage JSON export and coverage in the full engineering report. Combined review export captures coverage with references, actions and test evidence in one SQLite snapshot.
- Responsive layout, escaped text, stale-response/disposal guards and retained form values after a failed save.

## Verification

- **110 affected regression tests passed**, including the 25 focused new coverage/backend HTTP tests. Modules: coverage, coverage API, workspace API, sources/source API, actions API, design comparison API, test-evidence API and local launcher. The initial restricted HTTP attempt hit Windows socket sandbox permissions; the isolated rerun with loopback access passed.
- **9 real browser workflow groups passed** using temporary projects and provider transports that reject calls: automatic requirements; adding/reopening a missing-analysis check; outside-assumption/excluded mapping preserving an unmet criterion; linked navigation; report/export; conflicting save with retained form; changed dependency/stale result; draft/history guards; narrow-screen layout. Two harness corrections selected the intended fixture project and waited for actual revision loading. These were test setup/timing corrections, not weakened application assertions.
- **6 focused browser interaction groups passed:** wrong-project response rejection, disposed response, duplicate save prevention, retained form on conflict, read-only guards and report escaping.
- **7 final read-only checks passed** on the delivered main application. Browser writes/external requests were blocked; no browser errors occurred. Seven existing requirements appear and no founder coverage declarations were inserted.
- Original rows in all existing tables, configuration files and selected historical artifacts match the pre-build preservation snapshot. Twelve existing runs and two investigations remain unchanged. The only new main table, `project_coverage_versions`, is empty.
- No paid inference, research request, model activation or spending change. The approved cumulative Nebius ceiling remains USD29.50 and reservations USD2.30350988; reservations are not billed charges.

Ignored local evidence: `work/coverage-regression.json`, `work/coverage-browser-results.json`, `work/coverage-ui-results.json`, `work/coverage-current-results.json`, screenshots and `work/coverage-baseline.json` with its preservation checker. These are implementation checks, not external human engineering validation.

## Boundaries

Coverage records declared scope. It does not discover every mission hazard, independently prove physical model applicability, or supply a complete rocket checklist. User exclusions stay visible and do not erase numerical failures. Phase labels are organizational metadata. No new physical solver, powered atmospheric simulation or AI coverage reasoning was added.

This is a local delivery; no GitHub push is implied. The next proposed build is bounded powered atmospheric flight, with its own explicit assumptions and validation.
