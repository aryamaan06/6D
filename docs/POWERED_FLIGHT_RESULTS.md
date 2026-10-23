# Powered-flight delivery evidence

Delivered locally October 23, 2026 at http://127.0.0.1:8768/, build
`cedf1afe772d`. The app runs through the project's independent Python environment.
No GitHub push or hosted deployment is implied.

## Delivered behavior

The eighth maintained model adds vertical powered ascent and above-surface coast
with mass depletion, gravity, signed atmospheric drag and exact burnout handling.
Saved playback, six synchronized charts, criterion margins/allowances, numerical
diagnostics, source identity, reports and combined JSON expose the actual retained
calculation. The reference is explicitly created by the user; existing projects
are not populated with flight models automatically.

The shared authoring, revision invalidation, targeted rerun/reuse, scenario budget,
scalar chains, coverage and Assistant context support this model. Model-facing
Assistant evidence is compact and contains exact event/extrema witnesses and the
full artifact digest; the captured review retains the full trajectory. Offline
investigation/recheck acceptance passed. No live provider qualification is claimed.

## Verification performed

| Check | Recorded outcome |
| --- | --- |
| Affected regression suite | 292 tests passed, zero failures/errors/skips |
| Final startup correction | 61 affected workspace/API/launcher tests passed; overlaps the suite above |
| Analytic and conservation checks | Vacuum velocity/height at retained samples, mass/cutoff continuity, signed descent drag and coast energy passed |
| Separate numerical tool | Four constructed cases passed against SciPy DOP853, integrating mass independently |
| Isolated browser workflow | Ten groups passed: intake/run, charts, cutoff, keyboard/playback, export, draft, revision/history, requirement handoff, mobile containment and failed-grid behavior |
| Delivered main app | Six read-only groups passed with no browser errors, attempted writes or external requests |
| Separate-agent code audit | No material findings in mass/cutoff, drag, grid gates, downstream blocking or retained-history consistency; AI review, not human engineering review |
| Static checks | Selected Python compilation, both edited JavaScript syntax checks and Git whitespace checks passed |

The separate-tool results are recorded in
[POWERED_FLIGHT_REFERENCE_RESULTS.json](POWERED_FLIGHT_REFERENCE_RESULTS.json)
(a local file prepared for version control, not yet committed or pushed). Largest observed
sample differences across the four cases were approximately 2.57e-8 m in height,
1.18e-9 m/s in velocity and 1.48e-12 kg in mass. Acceptance limits were 2e-4 m,
2e-6 m/s and 1e-8 kg. These small discrepancies concern the same idealized
equations; they do not measure real-flight prediction accuracy.

Local detailed outputs: `work/powered-regression.json`,
`work/powered-browser-results.json`, `work/powered-current-results.json`, and
the desktop/mobile screenshots in `work/`. They are ignored development artifacts.
Core tests are `tests/test_powered_flight.py` and
`tests/test_powered_flight_workspace.py`. The optional SciPy suite is
`tests/test_powered_flight_reference.py`; instructions and sources are in
[the reference note](POWERED_FLIGHT_REFERENCES.md).

## Preservation and corrected startup behavior

The first main-app opening exposed an existing startup behavior: a verifier update
automatically recalculated the default project. This appended one genuine local
run. It is retained and disclosed; no record was deleted or rewritten. All twelve
original runs are byte-identical, and the current total is thirteen. The original
project/revision, two investigations, other recorded rows, configurations and
selected historical artifacts match the pre-build snapshot.

Startup now initializes checks only for a newly created default example. Opening
an existing project does not automatically rerun it after a source update; **Run
checks** remains explicit. Final read-only browser checks and the preservation
check confirmed no further append.

No paid calls were made. Super/global Nano selection and the cumulative allowance
remain unchanged: USD 29.50 ceiling, USD 2.30350988 reserved. Reservations are not
billed charges. No credentials were requested or exported for this milestone.

## Boundaries

This is a bounded one-dimensional model, not complete rocket physics, a landing
simulation, flight validation or evidence of mission success. Numerical allowance
and retained-data checks have the limits described in the reference note.
Independent human engineering review and real powered-flight AI evaluation remain
pending. Existing historical evidence and failed receipts remain unchanged.
