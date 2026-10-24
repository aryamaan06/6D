# Build B — planar ascent and prescribed steering

Delivered October 24, 2026. The new `guided_ascent` adapter adds horizontal motion and a supplied pitch programme. Existing vertical flight and Build A remain available. This is a bounded point-mass calculation, not a closed-loop launch GNC model.

## Try it

1. Refresh http://127.0.0.1:8768/ and open **Powered flight**.
2. Select **Planar ascent & steering**, then **Use constructed guided-ascent reference**.
3. Create the separate project and choose **Run checks**. Playback shows the saved surface-arc downrange/altitude path, with eight time-history charts and exact burnout sides.
4. Choose **Edit ascent inputs**, then **Edit draft**. Change **Final pitch angle** from **0.45 rad to 1 rad**. Preview impact, save the revision and rerun affected checks. Open Powered flight again to inspect the new path or select the requirement for its evidence.

This reference uses 32 coarse steps per nonzero segment, with 64 and 128 on the next grids. Its numerical support is checked from actual grid comparisons. No API key, external service or hand-written project JSON is needed. Creating or opening the reference does not automatically calculate it.

## Observed reference behavior

Both cases retain 1,000 kg initial mass, 700 kg dry mass, 20,000 N thrust and 250 s specific impulse. Pitch changes linearly from zero between 5 and 25 seconds, then holds until burnout.

| Supplied final pitch | Burnout altitude | Burnout signed downrange | Height criterion ≥5,000 m |
| --- | ---: | ---: | --- |
| 0.45 rad | 5,750.04 m | 2,042.38 m | Met |
| 1 rad | 4,397.68 m | 4,080.42 m | Unmet |

The baseline has ten supported criteria met and one launch-tracking requirement unassessed. The stronger turn increases downrange but reduces burnout altitude below the declared limit. It does not establish that the programme is optimal, stable or feasible for real hardware.

The pitch-only change executes ascent, the linked reference-density load screen and the static beam screening case. Ideal propulsion and independent thermal calculations are reused with their original execution origins. Unsupported launch-GNC evidence remains unassessed. Baseline receipts are retained unchanged.

## Delivered behavior

- Explicit body-centered inertial-plane states, supplied local-radial pitch convention, signed surface-arc downrange and vertical altitude.
- Central gravity, vector drag in the supplied stationary exponential atmosphere, constant engine performance and analytical propellant depletion.
- Exact segment boundaries at steering knots and fuel exhaustion, with before/after-cutoff samples retaining identical state and different thrust.
- Three-grid vector-position/velocity agreement, sampled metric allowances and unassessed findings when numerical support is missing or overlaps a criterion.
- Authoring/catalog support, transitive scalar links, targeted reruns, saved reports/exports, coverage labels and compact deterministic AI evidence. No live model qualification or paid AI work was performed for B.
- Saved path playback, eight charts, keyboard scrubbing, event selection, requirement handoffs and mobile containment. Drafts hide saved playback; historical playback remains readable with recalculation disabled in the new view.

The hidden Inspector is not rebuilt on the full-width guided-ascent page, avoiding duplicate trajectory markup and background requests for invisible controls.

## Verification record

The affected regression executed **293 methods**: 292 passed and one catalog fixture still expected eight models. The fixture's explicit contracts were expanded for the ninth adapter, and its entire 12-method authoring module then passed. All 293 distinct affected methods passed across those runs; the repeated 12 are not added to the total. The final interactive-reference API test was also repeated after selecting the checked 32-step demonstration grid and passed. This is targeted coverage, not a new full-suite result.

The covered modules include the new solver, saved/API workflow, legacy source-manifest compatibility, Build A, vertical flight, scalar chains, engineering/lifecycle, authoring, review overview, scenarios, investigation guards, evidence facts/roles and test comparisons. Local logs: `work/guided-regression.txt` and `work/guided-regression-results.json`; the initial failed fixture output is preserved.

The new solver tests include a closed-form vertical vacuum solution, reduction to existing vertical equations, mirrored steering, vector drag direction, vacuum-coast energy/angular momentum, exact knots/cutoff, invalid-domain rejection, numerical gaps and retained-artifact tampering. These checks do not prove applicability to real rockets.

Four separate SciPy DOP853 reference cases passed the declared position/velocity/mass tolerances, including the interactive 32-step case. The reference integrates mass as a fifth state and uses its own equations. [Source, assumptions and reproduction](GUIDED_ASCENT_REFERENCES.md) · [Input-bound results and source hashes](GUIDED_ASCENT_REFERENCE_RESULTS.json). SciPy is a development-only dependency; the ordinary app runtime remains standard-library-only.

Seven real-solver browser acceptance groups passed with no browser errors, external requests or paid calls. They cover template/mode selection, eight charts, keyboard/playback/cutoff controls, draft suppression, targeted rerun and altitude failure, inspector/report/export agreement, historical context, refresh, a negative turn, mobile layout and failed-grid propagation. Local output: `work/guided-browser-results.json`; screenshots: `work/guided-ascent-desktop.png` and `work/guided-ascent-mobile.png`.

Original project/source/investigation/receipt rows, provider settings and the cumulative Nebius reservation ledger were checked for preservation. No paid inference, search, metrics upload or deployment was performed. Older receipts remain readable; changed verifier sources require explicit recalculation before treating them as current evidence.

## Remaining boundaries

Steering is prescribed. Navigation, controller tracking, attitude, actuator limits, stability, lift, body rotation, wind, 3D motion, aeroheating, reentry and landing are unassessed. Downrange is a curved-surface projection, not vehicle geometry. Samples do not prove continuous extrema or rigorous error bounds. Constant thrust/Isp remain assumptions. Variable thrust and staging are the separately agreed **Build C**; they are not included in B.
