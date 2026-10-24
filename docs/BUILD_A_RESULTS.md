# Integrated rocket reference — Build A

October 24, 2026. This is a constructed review using five existing bounded calculation types. It adds a connected example and revision workflow, not new physics or a complete rocket simulation.

## Open it

1. Open http://127.0.0.1:8768/ and refresh. Choose **Rocket reference** under Project setup, or **Create rocket reference** in Review overview.
2. Choose a project ID/name and **Create project**, then **Calculate this revision**. Creating the project runs no calculations or AI calls.
3. Inspect the baseline, then choose **Stage reduced thrust**. The Changes view previews the 20,000 → 11,000 N edit and its dependencies. Choose **Save revision**, then **Rerun affected checks**.
4. Return to **Review overview**. Inspect the unmet burnout-altitude criterion, playback and calculation links. Choose **Stage thrust correction**, save and rerun; return to the overview to compare saved revisions or open the report.

Existing projects remain available in the project picker. Each reference import creates a separate project. Unsaved drafts and historical revisions cannot run the guided next edit. A customized reference remains editable through the ordinary workspace; its canned thrust sequence is disabled rather than overwriting custom inputs, sources, limits or links.

## What was calculated

| Configuration | Supported criteria met | Unmet | Unassessed | Burnout altitude |
| --- | ---: | ---: | ---: | ---: |
| Baseline, 20,000 N | 9 | 0 | 1 | 6,126.15 m |
| Reduced thrust, 11,000 N | 8 | 1 | 1 | 4,344.93 m |
| Restored thrust, 20,000 N | 9 | 0 | 1 | 6,126.15 m |

The criterion is **burnout altitude ≥ 5,000 m**. It is not final coast altitude. The launch-guidance tracking requirement remains unassessed in all three configurations.

Mass, specific impulse and thrust are shared by the ideal 500 m/s budget and vertical flight. Flight's maximum sampled speed feeds a separate reference-density drag screen. Its force is explicitly declared transverse at the tip of a hypothetical static cantilever screening article. The independent 200 W steady radiator is not linked to thrust or ascent heating.

The thrust-only edit recalculates propulsion, flight, drag and structure. Thermal is reused with its original execution provenance. The unchanged unsupported-GNC record may also be reused, retaining its unassessed status. Targeted reviews matched full recomputation in both changed configurations. Earlier baseline and failure receipts remained unchanged.

## Verification

- **55 distinct affected Python tests passed:** 14 new reference/profile/API tests; 18 existing calculation-chain, 11 flight-workspace, seven connected-review and five authoring-API tests. This is a targeted result, not a new full-suite result.
- Closed-form checks cover the ideal rocket equation, one-condition drag, Euler–Bernoulli beam response and Stefan–Boltzmann equilibrium. These check implementation of the declared equations, not applicability to real rocket hardware.
- Numerical-agreement failure was injected into the flight case: linked drag and beam findings remained unassessed instead of receiving unsupported quantities.
- HTTP checks exercised real saved revisions, summary digests, stale-base rejection, combined export and preserved historical receipts. Provider transports were forbidden.
- **Eight browser acceptance groups passed**, with no browser errors or external requests. They cover explicit intake and calculation, saved-result/draft separation, reduced-thrust failure, correction, playback, calculation links, comparison, combined export, historical guards, refresh and mobile containment. Detailed local output: `work/rocket-reference-browser-results.json`; screenshots: `work/rocket-reference-*.png`.
- Original workspace, source, investigation and receipt rows, provider configuration and Nebius reservation ledger were checked for preservation. No paid inference, Tavily search, LangSmith upload or provider activation was performed for A.

The previous full-suite result and its fixture corrections remain separately recorded in [VALIDATION_INDEX.md](VALIDATION_INDEX.md). No historical count is replaced by this targeted run.

## Limits

This reference does not supply simultaneous coupled physics, feedback, rocket-body structural validity, ascent aeroheating, launch GNC, horizontal steering, staging, reentry or landing. Sampled maxima are not proven continuous-time extrema. An ideal prescribed delta-v burn duration is different from the flight model's full-propellant burnout duration. Values and limits are illustrative; no NASA/ISRO/SpaceX or customer mission is represented. No launch authorization is given.

Builds B and C remain the separately agreed guided-ascent and variable-thrust/staging extensions. Build A does not complete those capabilities.
