# Compare recorded designs

Use **Compare designs** in the left sidebar to inspect two saved execution records or compatible hypothetical scenario cases. The view reads retained evidence; selecting or comparing records does not run engineering calculations, create revisions or request AI inference.

## Compare two records

1. Open the saved project and **Compare designs**.
2. Select the exact records for sides A and B. A run is identified by its saved revision and run identity; scenario cases are explicitly hypothetical and identify their study, case and baseline.
3. Choose **Compare recorded designs**. Review the record identities and compatibility messages before interpreting the numbers.
4. Inspect changed inputs, each requirement's result, criterion, margin and recorded status. Open the supporting context for assumptions, exclusions, model versions and source identities.
5. Export the captured comparison as JSON or print the comparison. Changing either selection invalidates the displayed comparison until it is compared again.

Only saved evidence is compared. A draft is not a calculated design, and a revision without a saved run needs its existing checks run before it can supply a comparison record. If only one record is available, save and review another revision or create an explicit scenario study through its existing workflow.

## What a trend means

For an unchanged `<=` criterion, margin is limit minus recorded result. For `>=`, it is result minus limit. A larger signed margin is more margin against that declared criterion. For exact `==`, the displayed quantity is the absolute difference from the target; a smaller difference is closer to the target, and only exact zero satisfies that equality. No tolerance is inferred.

An improved or reduced margin describes the recorded criterion under the supplied conditions. It does not establish which complete design is better, explain the physical cause of a difference or validate model assumptions. Changing an environmental input can change a margin without improving hardware.

If the declared limit changes, 6D shows **Criterion changed** instead of attributing the resulting margin change to a better design. Different operators, units, model/metric identities, calculation definitions or verification versions prevent a like-for-like improvement claim. For explicit scalar chains, this context includes upstream calculation definitions and evidence versions. Raw saved values and statuses remain inspectable with the relevant reasons.

Added or removed requirements are scope changes. Unassessed requirements remain gaps; missing or incompatible evidence is not converted to a failed or successful requirement. The comparison does not select a winning design or combine unrelated margins into a score.

## Hypothetical scenarios and history

Scenario cases remain hypothetical alternatives, not saved project revisions or physical-test results. Compatible case comparisons share the same saved baseline run. A baseline run can be compared with its own scenario case; different scenario baselines are flagged as incompatible for trend interpretation.

Historical records retain their original source versions and assumptions. A comparison can preserve those values while warning that they do not match the current maintained implementation. The record identities and captured export describe the selected evidence, rather than automatically following a later rerun.

Input units and provenance are shown exactly as supplied. Unit conversion, arbitrary scenario equivalence, causal attribution, physical validation and whole-mission readiness are outside this comparison feature.
