# Targeted versus full recalculation verification

## Acceptance contract

An engineer changes supplied design records, saves a revision and runs affected checks. The resulting engineering review must equal a fresh full evaluation of that exact saved revision. Reusing an unaffected calculation must not change any model result, requirement finding or evidence dependency. The baseline project and its earlier review must remain unchanged.

Before accepting this milestone, run at least 1,000 reproducible generated edit cases across the seven existing maintained model types and scalar chains. Include input values/units/sources/bindings, requirement criteria, model definitions, connection changes and structurally invalid records. Record the seed, generator/comparator/source hashes, operations, outcomes, elapsed time and case identifiers. Persist counterexamples and fix confirmed product discrepancies before reporting a pass.

## Comparison protocol

1. Use a new isolated SQLite workspace for each base/edit pair, avoiding growing-history quadratic work and any founder-data modification.
2. Validate the expected structural acceptance of each generated base and edited snapshot using the project contract. A structurally valid snapshot may still produce numerical invalid-input or unassessed results.
3. Save and review the base through the real `WorkspaceStore` path. Preview and save the supplied edit, then run the real targeted workflow.
4. Independently orchestrate a full evaluation with `engineering.evaluate_models(saved_snapshot)` and `lifecycle.review_project(...)`. This reference must not call the workspace reuse-key or impact-selection helpers and must evaluate all models, including unchanged models.
5. Compare the complete review, including exact numerical values, findings, model artifacts, assumptions, exclusions, resolved chain values, source identities, dependency fingerprints and review digest. Do not round values or strip evidence fields to make a mismatch pass.
6. Check that reported execution/reuse IDs partition all models, execution origins are consistent, the original receipt remains unchanged, and the stored current receipt survives reopening. Validity of receipts is checked separately from comparison.
7. Structurally invalid edits must be rejected by both the full-reference validation path and workspace preview/save; no new revision or result may appear. Adapter-domain failures are assessed normally and must match the full calculation.

Workspace run IDs, timestamps, execution/reuse lists and execution origins describe orchestration history rather than engineering equivalence. They are checked by their own invariants, not compared with an invented fresh-run identity. The complete lifecycle review has no such exclusions.

## Interpretation and boundaries

This is a differential/metamorphic regression benchmark of the existing incremental workflow against the same maintained calculators invoked in full. It can detect invalidation, reuse, ordering, persistence and evidence-binding defects. It is not an independent validation of the calculators' physics, real-spacecraft suitability, model applicability, hosted-AI explanations or market demand.

Generated cases are stratified and seeded; 1,000 passing cases do not establish universal correctness or a statistical failure probability. Finite distributions and topology bounds must be disclosed. Sequential edit histories and numerical extremes are only covered where explicitly included. External analytical/tool benchmarks and live AI evaluation remain separate milestones.

The benchmark requires no network, credentials or model inference. It does not change production project storage, providers, allowances or the application interface.
