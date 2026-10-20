# Model applicability and accuracy safeguards

Acceptance written before implementation, October 19, 2026.

User task: an engineer supplies an orbital design and explicit numerical tolerances, runs local checks, and can distinguish an unmet criterion from missing or inadequate numerical evidence in the workspace and exported report.

- Preserve the existing workspace, immutable history, seven models and provider/spending settings. No paid inference or customer-data changes.
- New orbital reviews require explicit positive position/velocity grid-agreement tolerances and their source. No default user accuracy requirement is inferred.
- Compare aligned state vectors on three progressively finer grids while preserving the selected finest trajectory and existing solver limits. Record differences and observed refinement; conservation alone cannot qualify accuracy.
- Missing criteria, unavailable refinement or incompatible grids remain unassessed. Exceeded tolerances or unsupported refinement remain explicitly unresolved. Numerical grid agreement is not a rigorous true-error bound or validation of the physical model.
- A requirement too close to its limit for the declared allowance must not receive a pass. Exact equality cannot be established with a positive accuracy allowance.
- Deficient orbital evidence cannot revive a pass through calculation links, scalar interfaces, scenarios, test prediction comparisons or Assistant explanations.
- Old orbital v1 receipts remain internally verifiable with their original findings. Show when numerical accuracy was not assessed rather than rewriting history.
- Show model assumptions, physical applicability gaps and reference context in Inspector and Reader/Report. Reference examples are bounded comparisons, not proof for the user's design.
- Verify missing/tight/adequate tolerances, near-limit criteria, tampered receipts, targeted/full rerun agreement, immutable history, report/JSON projection and the actual browser workflow.

Numerical-method context: [NASA temporal convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/tempconv.html) and [NASA grid convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html). Three-grid refinement principles are applied here to time integration, not represented as NASA validation of this implementation. The observed-order interval is a declared software policy, not an aerospace standard or physical uncertainty estimate.


## Delivery verification — October 20, 2026

Delivered local build **5f3fd17543b0**, runtime `3a55967ce8e654dff63d777cad80548d2b536377c8eeb629ce5bf8839b22dc98`.

- The full automated run exercised **800 tests**. Initially, 797 passed; two old schema assertions expected no applicability context, and one Windows localhost connection was aborted during a cross-origin rejection test. The assertions were updated for the intended contract, and all three affected test groups (**52 tests**) passed on recheck. No production change or automatic transport retry was introduced for the connection interruption. No failed check remains open.
- **Six browser acceptance groups passed** against an isolated temporary database with provider execution forbidden: complete/partial/missing accuracy criteria; shared-draft revision and rerun; tight tolerances; allowance-overlapping criteria; Inspector/Canvas/Table/Reader/print-media/JSON disclosure; immutable baseline and document widths. No browser errors, external requests or paid-provider endpoints occurred.
- The **30 published-reference/domain checks passed** against the updated sources. The new receipt is `artifacts/published-benchmarks/accuracy-safeguards.json`, digest `14119cc15aed32c013e5527ac2745b9a679e9e1c55abc1c242d071392c690211`. The earlier benchmark receipt was preserved.
- The existing project's database rows and provider/allowance configuration hashes remained unchanged. Paid calls: **zero**. Preservation receipt: `work/accuracy-preservation.json`; browser receipt: `work/accuracy-browser.json`; delivery summary: `work/accuracy-delivery.json`.
- Actual PDF creation/rendering was not tested; native print-media rules and expanded disclosure visibility were checked. Live AI explanation evaluation remains a separate pending milestone.

These checks verify the bounded workflow and numerical receipt policy, not physical model validity or complete spacecraft/rocket verification.
