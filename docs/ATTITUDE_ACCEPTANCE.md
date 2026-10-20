# Single-axis spacecraft pointing — acceptance

Delivered October 18, 2026, Asia/Calcutta. The numerical implementation, integrated automated suite, post-fix browser checks and founder-state preservation audit passed. Live build **04103cfe02e1**, runtime `41c46e99d589b3cebc3f83264e818fd5b9ed5bf0074a3ea0ccabb7bd453b0151`, is verified at `http://127.0.0.1:8768/`.

## Implemented contract

The maintained `attitude_control` adapter calculates one rigid principal axis with constant inertia, a fixed unwrapped angle target, ideal continuous proportional/rate feedback, symmetric actuator torque clipping and an explicitly supplied constant disturbance. Thirteen explicit input bindings use exact SI unit contracts. Nine saved scalar metrics describe final and sampled pointing error, angular rate, requested/applied torque and the fraction of saved samples whose command was clipped. The declared assessment window reports its first included sample and sample count; neither interpolation nor settling time is inferred.

Independent coarse/fine classical RK4 runs compare error and rate at common times against supplied numerical tolerances. Resolution, finite arithmetic, state-magnitude and underflow guards can abstain with `invalid_inputs`, empty metrics and no completed response. An unmet engineering criterion remains a completed calculation with a separate `not_met` requirement finding. Numerical agreement is not a proof of absolute accuracy or physical validity. See [ATTITUDE_MODEL.md](ATTITUDE_MODEL.md) for the equations, all units, numerical contract, analytic witnesses and exclusions.

The saved `attitude_response` artifact carries the full fine-grid history, inputs, solver settings, diagnostics, source fingerprint, assumptions and exclusions. History reads validate the retained record without reintegrating. Supported metrics participate in immutable revisions, targeted reruns/reuse, explicit scalar interfaces, scenario alternatives, scalar measurement comparisons, scoped Assistant context and reports. No downstream input is changed automatically. The shared authoring catalog supports explicit control models and requirements; unsupported generic GNC/navigation requirements remain unassessed.

## Confirmed automated verification

- **20 kernel tests passed** in `tests/test_attitude.py`. Independent references include critical damping at every saved sample, free rotation, constant external torque, continuously clipped torque with quadratic angle, undamped cosine motion with fourth-order refinement, and an overdamped pair of exponentials. Other checks cover disturbance after clipping, release and reversal of saturation, sign symmetry, stationary equilibrium, unwrapped angles, assessment-window endpoints, invalid units/bindings/domains, resolution and numerical-tolerance abstention, deterministic nonmutation and corrupted artifacts.
- Two independent-review findings were corrected before the final suite: an initially excessive error now triggers the same computational magnitude limit as later states, and nonzero arithmetic that underflows to zero cannot silently produce an apparently stationary response. Dedicated regressions cover both cases. No engineering requirement limit is relaxed.
- **13 workspace tests passed** in `tests/test_attitude_workspace.py`. They cover persistence/reopen without integration, a control-only targeted rerun with independent thermal evidence reuse, limit-only reassessment, invalid-input and unit gaps, absent/rehashed/corrupt artifacts, the required new source manifest, and readability of historic five-file orbital evidence.
- The catalog/preflight test verifies all thirteen roles and nine metric units without calculating. A torque sweep preserves the canonical baseline; scalar measurements preserve measured compliance separately from agreement with the declared prediction. An injected offline Assistant transport reads a bounded evidence projection and rechecks only the selected control model. This verifies context and orchestration, not live Nemotron performance.
- The **complete integrated suite passed: 712 tests in 115.224 seconds**, using `python -m unittest discover -s tests -v`. Retained log: `work/attitude-final-tests.log`. Earlier source-manifest assertions were updated to include the new solver source; legacy manifest support remains tested. No application guard was weakened.

## Browser and delivery verification

The final real Chrome acceptance run, repeated after both numerical edge-case corrections on a fresh isolated server, passed **six groups**, with no page errors or paid calls. Receipt: `work/attitude-browser.json`; script: `work/check-attitude-workflow.mjs`. It used an isolated temporary database, prohibited provider execution and blocked external/AI requests.

The six groups exercised:

1. Creating the constructed reference through the actual UI, running local checks, and inspecting the three saved histories, assessment window, numerical diagnostics and provenance.
2. Editing torque in the shared draft, suppressing stale plots, saving a revision, rerunning only control, and observing an unmet pointing criterion while preserving independent thermal evidence and the original history.
3. Opening the selected requirement and its scoped Assistant without starting inference.
4. Inspecting clipped, released and reversed actuator evidence separately from requested torque, at desktop, tablet and mobile widths.
5. Reading the integrated report and full JSON response, and generating a native PDF containing tables and graphs.
6. Producing an explicit unassessed gap from invalid inputs and reopening the original saved response from revision history.

- **Two additional blank-project authoring groups passed** through the real UI: `work/check-attitude-authoring.mjs`, receipt `work/attitude-authoring-browser.json`. These verify the new adapter through shared authoring rather than relying only on template import.
- **Nine existing project-authoring regression groups passed** in `work/check-project-authoring.mjs`, receipt `work/project-authoring-browser.json`. Existing editing, preflight and save behavior remains covered alongside the new control model.
- **Ten existing orbital-workflow browser regression groups passed** in `work/check-orbit-workflow.mjs`, receipt `work/orbit-workflow-acceptance.json`. No paid calls were made.
- The final browser run regenerated the native **13-page PDF**. Its graph and torque/table pages were rendered and visually inspected, along with the mobile layout: values, column content and curves remain legible. Desktop, tablet and mobile document-width checks found no overflow. Test artifacts include `work/attitude-integrated-report.pdf` and the attitude screenshots under `work/`.
- The exact owned repository server command was verified before restarting it in the background. **GET-only Chrome smoke verification** at the normal address confirmed the new build, current runtime and no restart requirement, with no errors, blocked requests, production mutation or paid calls. Receipt: `work/attitude-live.json`.
- The final preservation audit compared every row in every founder project table against the pre-milestone SQLite backup. All rows match: 1 project, 1 revision, 8 runs, 2 investigations, 2 model comparisons and 1 simulation; scenario and test-comparison tables remain empty. The spending ledger, Token Factory configuration and reviewed Assistant-selection file hashes are identical. Receipt: `work/attitude-preservation.json`.

Open `http://127.0.0.1:8768/`, refresh, and confirm build **04103cfe02e1**. Choose **Guidance & control → Open constructed reference → Create project → Run saved checks** for a separate analytical example. Test artifacts under ignored `work/` are development receipts, not user or flight data.

## Scope and spending

This is the first bounded quantitative control model, not full guidance, navigation or three-axis attitude control. It excludes sensors/estimation, digital controller delays, wheel momentum, actuator dynamics, flexible bodies, moving targets, environmental torque prediction, coupled orbit/thermal/power physics, rocket landing, uncertainty and mission-readiness certification. The reference is constructed analytical test data, not a real spacecraft. Sampled extrema and clipped-sample fractions do not establish continuous-time bounds or durations.

No paid provider calls, model-selection changes or spending-limit changes are needed for this milestone. The reviewed application Assistant remains separate from the local calculation. Its new control evidence context has offline validation only. No credential is requested, printed or retained by the tests; no publication or deployment is included.
