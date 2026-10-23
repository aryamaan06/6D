# Unified design comparison acceptance

## User task

An engineer chooses two exact saved records, compares supplied inputs and requirement findings, checks whether the evidence is comparable, and exports the comparison without recalculating either design or changing its numerical verdicts.

## Acceptance cases

1. List saved run records and retained scenario cases only for the chosen project and selected revision boundary. Distinguish saved revisions/runs from hypothetical study cases, and show catalogue limits or omitted history. Unreviewed revisions do not acquire invented results.
2. Pin selections to explicit run identities or a study/case identity. Refuse the same record on both sides. Refuse cross-project, future-revision, invalid-case and corrupted-record selections without recalculating or replacing records.
3. Compare two saved revisions with compatible model and requirement definitions. Preserve each side's actual requirement status, metric, operator, limit, units, source identity, assumptions and excluded scope.
4. Show added, removed, unchanged and changed inputs, including source-label and unit changes. Do not subtract quantities with incompatible units or silently convert them. Preserve exact display text for recorded large integers and finite quantities rather than allowing browser formatting to change the source number.
5. Verify margins independently for `<=`, `>=` and exact `==`: limit minus result, result minus limit, and absolute target difference respectively. Equality gets no inferred tolerance. A greater signed margin or smaller equality difference can be labelled improved only against an unchanged comparable criterion.
6. Change a requirement limit while leaving its calculated metric unchanged. Show the two original criteria and margins, label the criterion change, and do not call the design improved merely because a limit was relaxed. An operator, metric, model identity/definition, unit or verification-version change also prevents a like-for-like trend claim. For scalar chains, preserve and compare upstream identities, definitions, assumptions and evidence versions while allowing supplied numeric input values to differ.
7. Keep missing, unsupported, accuracy-limited and otherwise unassessed findings distinct from calculated failures. Do not infer a pass, margin or improvement from diagnostic quantities that the canonical finding did not assess.
8. Present added and removed requirements as scope changes, not successes or failures. A completely unassessed alternative cannot win through a favourable aggregate count. No weighted ranking, automatic best-design label or mission-readiness percentage is produced.
9. Compare compatible cases from the same scenario baseline and compare a scenario case with its exact baseline run. For different scenario baselines, preserve inspectable raw evidence but flag incompatible context and suppress numeric trend conclusions. Cases remain visibly hypothetical throughout the view and export.
10. Preserve historical records while showing current implementation/version limitations honestly. Never present an older source/version match as proof that current physics, numerical accuracy or model applicability has been verified.
11. Read all selected evidence within a consistent database snapshot, preserve its identities and cover the comparison payload with a digest. Export the exact displayed comparison rather than refetching a later “latest” run. Print the relevant criteria, units, compatibility warnings and supporting context.
12. Editing either selection invalidates the previous comparison and disables its exports until a new explicit comparison succeeds. A delayed response, refresh or project change cannot overwrite the current selection with stale results. Text and source labels render safely, and narrow layouts keep tables within an intentional scroll region.
13. Show useful empty/error guidance when fewer than two saved records exist or no comparison is meaningful. Links to authoring/scenarios do not automatically execute calculations or create fixtures pretending to be founder evidence.
14. Preserve all existing project, revision, run, scenario, action, source, investigation, configuration and spending records. Comparing, exporting and printing require no API connection, paid call or new engineering calculation.

## Interpretation limits

This is a recorded-evidence comparison, not independent validation of either design. Trend labels describe a declared criterion under supplied conditions; they do not establish causation, broader physical equivalence, hardware quality, whole-vehicle validity or mission success. Actual observed checks belong in a separate milestone results document.
