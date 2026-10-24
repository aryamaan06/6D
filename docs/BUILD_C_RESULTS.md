# Build C — variable thrust, fuel accounting and serial staging

Delivered October 24, 2026. The separate `staged_ascent` adapter supports supplied linear thrust programmes and one to four serial stages. The nine earlier adapters and A/B examples remain available.

## Open and try it

1. Refresh http://127.0.0.1:8768/ and open **Powered flight → Variable thrust & staging**.
2. Choose **Use constructed staged-ascent reference**, create the separate project and choose **Run checks**.
3. Use **Recorded event** to inspect stage-one cutoff, separation before/after and stage-two ignition. Attached mass drops from **530 kg to 380 kg** at separation, with the same position and velocity on both sides. The upper stage ignites after the supplied two-second coast.
4. Choose **Edit stage & thrust profile**. Stage masses, per-stage Isp, delay and thrust-segment duration/start/end values are ordinary form fields. New stages and segments begin blank. Changes remain local to the form until **Apply profile to draft**.
5. For the constructed counterexample, change **Stage 2 specific impulse from 280 s to 220 s**, apply, preview affected checks, save and rerun. The 50,000 m burnout-altitude criterion changes from met to unmet. Earlier receipts are preserved.

The form supports one to four stages and one to six segments per stage. It preserves existing source/unit labels and unrelated inputs, warns about shared inputs, rejects incomplete/nonfinite/negative values, and does not replace calculated stage links. Remaining global ascent inputs use the existing table/Inspector editor. Opening a form or importing a reference does not calculate or call AI.

## Actual constructed results

| Quantity | Upper-stage Isp 280 s | Upper-stage Isp 220 s |
| --- | ---: | ---: |
| Initial attached mass | 1,030 kg | 1,030 kg |
| Propellant consumed | 700 kg | 700 kg |
| Discarded stage-one dry mass | 150 kg | 150 kg |
| Final retained mass | 180 kg | 180 kg |
| Final-stage burnout altitude | 52,619.66 m | 41,910.45 m |
| Burnout-altitude criterion ≥50,000 m | Met | Unmet |

The baseline reference already exceeds three inherited reference-density drag/beam screening limits. Those are retained as **unmet engineering criteria**, not hidden, loosened to produce a green screen or presented as a software error. The baseline totals are eight criteria met, three unmet and one unassessed; lower upper-stage Isp adds the burnout-height violation. Launch-controller tracking remains unassessed throughout.

The drag/beam chain remains a separate scalar screening case using maximum retained speed and supplied reference density, not actual maximum trajectory drag or whole-vehicle structures. The radiator remains independent; it is reused after profile changes. The staged calculation itself accounts for propulsion mass/impulse, so the example does not falsely use a single-stage ideal rocket budget to certify the complete stack.

## Delivered calculations and workflow

- Analytical impulse and fuel consumption for each supplied linear thrust segment; exact exhaustion can truncate an overlong programme. Insufficient impulse and unsupported domains remain input/model gaps.
- Payload plus all initial wet stages, separate consumed fuel and discarded dry mass, retained final-stage dry mass, and explicit ordered event sides. Ideal separation imposes no velocity impulse.
- Planar central gravity, stationary exponential atmosphere, vector drag and prescribed local-radial steering. The global coefficient/area remain supplied constants through staging.
- Segmented RK4, three retained aligned grids, sampled metric allowances and numerical-gap propagation to requirements and scalar dependents.
- Dynamic catalog/preflight/bindings, stage-profile forms, mass/thrust histories, exact-event selection, saved path playback, comparison-compatible revisions, Inspector, complete reports/exports, compact deterministic AI evidence and test-observation support.
- Draft playback suppression, stale-base protection, preserved history and disabled editing/recalculation for historical records in the new flight view.

## Verification

**320 distinct affected Python methods passed across the scoped runs:** 14 solver tests, 84 engineering/lifecycle/chain/staged-workflow tests and 222 remaining API/A/B/authoring/review/scenario/evidence tests. The initial 222-method run had one outdated catalog fixture that did not allow the new `profile` field; its corrected 12-method authoring module passed. Repeated methods are not added to the total, and this is not a new full-suite discovery result.

Solver checks include closed-form single-stage vacuum motion, summed one-to-four-stage ideal delta-v and mass budgets, variable-thrust fuel roots, exact fuel exhaustion at a declared thrust knot, zero/nonzero delays, event-side mass/velocity continuity, steering knots during coast, mirrored trajectories, conservation, numerical gaps and artifact tampering. A rounding edge at fuel exhaustion coincident with a thrust knot was fixed and rechecked.

Four separately written SciPy DOP853 six-state cases passed declared sampled state, mass and fuel-event-time tolerances. The reference integrates mass and propellant and locates fuel exhaustion through its own terminal event; it does not use the production analytic root or stage plan. [Equations, assumptions and reproduction](STAGED_ASCENT_REFERENCES.md) · [Recorded inputs, differences and source hashes](STAGED_ASCENT_REFERENCE_RESULTS.json).

Eight actual-solver browser groups passed with zero browser errors, external requests or paid calls: explicit intake, stage-event controls, form edits, preview/save/rerun, reporting, historical/refresh context, mobile layout and numerical-gap propagation. Pure UI fixtures are separate from these actual-solver checks.

Public scoped summary: [validation/BUILD_C_CHECKS.json](validation/BUILD_C_CHECKS.json).

Local evidence: `work/staged-adapter-regression-results.json`, `work/staged-regression-results.json`, corresponding text logs, `work/staged-browser-results.json`, and `work/staged-ascent-desktop.png`, `work/staged-ascent-mobile.png`, `work/staged-profile-mobile.png`. Original project/source/investigation/receipt rows, provider configuration and the Nebius reservation ledger were checked for preservation. No paid inference, search, metrics upload, deployment or provider activation occurred.

## Limits and next scope

These are constructed inputs and criteria, not a historical launch or customer mission. Serial stages, constant per-stage Isp, ideal zero-impulse separation, fixed global coefficient/area and prescribed steering remain assumptions. Parallel boosters, crossfeed, separation mechanics, discarded-stage recovery, closed-loop launch GNC, attitude/stability, aeroheating, reentry and landing remain unassessed. Passing a declared criterion is not mission approval.

The agreed next functional item is **D: project-wide AI investigations**. C does not start D or the separate connection/hosting builds.
