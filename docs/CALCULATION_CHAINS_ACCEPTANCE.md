# Calculation-chain acceptance — October 19, 2026

Delivered local build **c6fb931d0af2**, runtime `8fec80080d75abee85ee4c4182ce916561c4f6c76f4a8f5967553955d0244952`, at http://127.0.0.1:8768/. Health reports no restart required. Production confirmation used GET-only browser access; no project creation, revision, calculation or provider call was made against founder storage.

## Delivered behavior

Supported scalar outputs can feed explicitly selected downstream parameters through unit-matched links with a supplied engineering rationale. The Calculation chains page provides the dependency graph and shared-draft link editor. Server preflight rejects malformed links, missing source metrics, mismatched units and cycles. Execution follows dependency order, retains resolved values and ancestor provenance, and propagates missing evidence as not assessed. A valid calculated value remains usable when its source requirement is not met.

Source input/definition/rationale changes invalidate dependent evidence, even when values happen to remain equal. Unrelated branches and requirement-only changes reuse unchanged calculations. Scenarios, test-evidence applicability, offline Assistant context/rechecks, playback exports and Reader/JSON/PDF reports preserve the same declared dependencies. Generic model editing retains links; referenced source deletion is guarded. Historical source sets remain readable without rerunning numerical solvers.

## Actual validation

- Full automated suite: **741 tests passed**, including 29 new chain core/integration tests. Receipt: `work/chains-final-tests.log`.
- New browser workflow: six acceptance groups passed. Covers creating/running the constructed reference, analytical drag-to-beam values, transitive edit/save/rerun, thermal reuse, immutable history, editing/removing/recreating links, missing upstream results, mobile overflow and report/JSON/PDF output. Receipt: `work/chains-browser.json`.
- Browser edge cases: two groups passed for imported colon-containing IDs and rejecting a reciprocal cycle without losing the valid draft or modifying the saved revision. Receipt: `work/chains-edge-ui.json`.
- Existing browser regression: authoring nine groups, orbital workflow ten groups, attitude/control six groups passed. All ran against isolated test storage with provider routes blocked.
- Printed eight-page report retained the chain's resolved force, rationale and source identities. Page four was rendered with Poppler and visually inspected; text and long digests fit without clipping. PDF: `work/chains-integrated-report.pdf`.
- Read-only running-app check: the page, reference template, existing report and visible build identity loaded without JavaScript errors. Receipt: `work/chains-live.json`.

The analytical reference uses constructed data: 20 N drag feeds 400000 Pa beam stress and 1/3750 m deflection. Doubling relative speed gives four times each result. Its deliberately exceeded drag criterion does not suppress the valid load. Negative density makes drag invalid and the dependent structural check unassessed. These checks validate implementation against the stated formulas; they do not validate a real aerodynamic coefficient, beam geometry or vehicle.

## Preservation and limits

All records in the October 18 pre-chain backup are preserved byte-for-byte. The live database also contains one additional run timestamped `2026-10-18T16:03:45.380625+00:00`, predating this October 19 completion session; it was preserved. Final counts: one project, one revision, nine runs, two investigations, two model comparisons and one simulation. No scenarios or test-comparison rows were added to founder storage. Budget ledger, Token Factory configuration and Assistant selection hashes match the backup. See `work/chains-preservation.json`.

**Zero paid inference calls.** No provider/model routing, allowance, deployment or Git publication changes. Starting the local server leaves the private AI connection empty; local calculations need no key.

This is explicit one-way scalar chaining among maintained calculators. It is not simultaneous multiphysics, vector/frame conversion, time-series coupling, automatic load-case validation, whole-vehicle simulation or launch approval. No broader engineering coverage is implied by the chain graph. SI superscript display and final visual polish remain deferred.

## Open the result

Refresh the local address and confirm build **c6fb931d0af2** in the footer. Choose **Calculation chains → Open constructed reference → Create project → Run saved checks**. This creates a separate example and leaves the existing project intact. For an existing applicable project, choose **Edit in shared draft → Add calculation link**, supply source/metric/receiving parameter/rationale, save the revision and run checks. Reader/Report shows the retained evidence; Changes previews affected dependencies.
