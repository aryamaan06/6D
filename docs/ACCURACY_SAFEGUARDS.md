# Model assumptions and orbital accuracy safeguards

This increment brings bounded reference context and numerical gaps into the existing workspace. It does not add a new physics model or claim complete vehicle verification.

## What users can do

In the orbital model's existing definition editor, supply a position tolerance in metres, a velocity tolerance in metres per second, and their source or rationale. All three fields may be left blank; blank is never a default or zero. Save the shared draft as a revision and run checks. Changes to these criteria invalidate the orbital result and downstream calculation dependencies while preserving unrelated evidence and historical records.

The existing `steps` input is the finest grid. Three-grid comparisons require a value divisible by four and at least 64; all three runs must also satisfy the solver's existing domain guards. There is no automatic step increase. Inspect the recorded reason when a coarser grid cannot run.

Inspector and Reader/Report show saved assumptions, model scope, enforced input guards, physical applicability questions requiring external evidence, source links, declared numerical tolerances, aligned-grid differences and observed refinement orders. These references cover selected idealized examples, not the supplied design. Current-catalog context for old reports is labelled separately from evidence frozen with a new result.

## Meaning of the result

| Display | Interpretation |
| --- | --- |
| Met | The sampled calculated criterion meets its declared inequality with room for the supplied numerical allowance, conditional on the recorded assumptions. |
| Not met | The criterion is violated beyond that allowance; this is distinct from a calculation or evidence gap. |
| Accuracy not assessed | Required tolerances or usable refinement evidence are missing. The trajectory may still be inspected. |
| Insufficient accuracy | Grid differences/refinement do not meet the declared policy, or the declared allowance overlaps the requirement limit. |
| Not assessed | Another unsupported model, input, unit or missing-evidence condition prevents comparison. |

An exact equality cannot be established with a positive numerical allowance. Use justified explicit upper/lower criteria instead. No physical threshold, material validity range or mission tolerance is invented by 6D.

The numerical assessment compares signed position and velocity vectors at aligned stored times on quarter, half and full grids. Each observed order must lie within the declared 1.8–2.2 policy and the worst middle/fine vector differences must not exceed the user-supplied tolerances. These are numerical grid-agreement checks, **not rigorous true-error bounds**, continuous-time guarantees or physical validation. No result is qualified by conservation diagnostics alone. See [the numerical contract](ORBIT_ACCURACY.md) and [acceptance criteria](ACCURACY_SAFEGUARDS_ACCEPTANCE.md).

## Constructed demonstration

The orbital reference template now uses 2048 finest steps and explicitly illustrative allowances of 500 m and 0.6 m/s. These are demonstration values rather than recommended engineering requirements. The 1024/2048 aligned comparison measures approximately 432.55 m and 0.44626 m/s, with observed orders approximately 2.0. Missing criteria or a 1 m position tolerance leave its orbital requirements unresolved. A threshold within 100 m of its predicted radius is also unresolved under the 500 m allowance.

The published eight-period case cannot complete this three-grid assessment within the current solver limits and remains numerically unassessed. This increment exposes that limitation; it does not repair long-orbit integration accuracy. The earlier [published benchmark report](PUBLISHED_BENCHMARK_RESULTS.md) remains a historical comparison for its recorded source fingerprints.

## Evidence boundaries

New orbital adapter v2 results retain the finest trajectory, two available coarser trajectories, exact criteria, comparison arithmetic, order estimates, source fingerprints and explicit limitations. New canonical findings are gated by that receipt. Missing or inadequate accuracy also blocks downstream scalar calculations and interfaces, prediction-agreement evidence and unsupported Assistant interpretations. Measured test compliance stays separate from numerical prediction agreement.

Playback and scoped Assistant contexts carry compact summaries with declared omissions. Full reference trajectories remain in the canonical review and evidence JSON. Printing the Reader report includes the detailed assumptions and accuracy disclosures. No paid AI call is needed for these calculations or report views.

Historical orbital v1 records retain their original findings and remain inspectable without rerunning the current solver. The interface warns that their numerical accuracy was not assessed; it does not reinterpret a historical pass as a new accuracy qualification. Unsigned digests check internal consistency, not authorship or authenticated approval.

Physical applicability, source-data quality, unmodelled effects, between-sample constraints, real-vehicle validation and mission success remain outside this numerical check. See [the applicability audit](MODEL_APPLICABILITY_AUDIT.md).
