# Connected workspace delivery — October 15, 2026

Arya accepted the provisional interface and authorized the next functional build. The connected application replaces the isolated preview at http://127.0.0.1:8768/ . Open-6D.cmd starts or reuses the same local service. Delivery build: `3e3ea4a72bd9`.

## Implemented

- Local SQLite storage for supported projects, immutable revisions and calculation receipts. Default storage is `.local/workspace.sqlite3`; browser and server restarts preserve saved records.
- JSON import and reference templates with explicit identity, units, source labels, model bindings and requirements. Existing project IDs cannot silently overwrite stored projects.
- Shared Canvas, Table, Reader and inspector records, with declared dependency links and revision selection.
- Draft editing of numerical inputs, units, sources, requirement limits, comparison operators and criticality. Draft impact previews do not run calculations or save revisions.
- Saved-revision checks through the existing ideal-propulsion, static-cantilever, radiative-equilibrium and drag adapters. Unchanged model results are reused only after checking their definitions, complete input records, adapter versions and verifier source hashes. Receipts retain original execution run/revision identities.
- Current and historical findings, comparison charts, report reader and downloadable project/evidence JSON. An unassessed requirement is distinct from a calculated limit violation.
- Optimistic revision conflicts, bounded strict JSON requests, loopback host/origin checks and allowlisted assets/APIs. No arbitrary file serving, uploaded code execution or live inference endpoint is exposed.
- Runtime/source protection: changed application code requires restart before mutation; changed loaded verifier sources/versions prevent new evidence. Source changes during a calculation prevent its receipt being saved.

## Verification

The full standard-library regression suite passed: **268 tests**. This includes 18 focused workspace persistence/calculation tests and 13 HTTP tests. Existing numerical audit, provider protocol, limits and CLI tests remain passing. No test invoked a paid provider.

An actual headless Chrome walkthrough exercised the isolated test server using separate storage:

1. Loaded real initial calculations with six met requirements and an explicitly unsupported control requirement.
2. Changed heat input to an arbitrary constructed 700 W and edited its source without losing editor focus. Preview affected only the thermal dependency and left saved records unchanged.
3. Saved a new revision with no current result while preserving old evidence.
4. Executed only the thermal adapter, independently checked its temperature formula, and verified unchanged model execution origins. The thermal limit was unmet while control remained unassessed.
5. Downloaded an evidence report matching the stored review digest, refreshed, and selected the original unchanged revision.
6. Checked a shared thrust edit affected propulsion and structural bindings, then discarded it.
7. Imported a project with custom input/model/requirement IDs and literal HTML-like text; calculated its results, checked safe text rendering and reopened it.
8. Changed a heat unit to an unsupported unit and confirmed invalid inputs/unassessed coverage rather than an invented conversion or vehicle-defect verdict.
9. Checked mobile navigation and absence of document overflow, and observed no browser JavaScript/CSP errors.

The delivered 8768 service was separately checked for its actual connected service identity, current runtime, visible build identity, saved default review, shared views, refresh and mobile table scrolling. The launcher reused the running service. Test projects were confined to separate storage under ignored `work/`; the delivered database starts with the constructed default project.

## Material boundaries and next work

The default model-derived system groups are not a general hierarchy editor. Intake does not parse CAD/PDF or execute arbitrary solver repositories. Scalar component calculations are not a full rocket simulation or proof of mission readiness. Source descriptions are supplied labels, not authenticated provenance. Storage has no customer accounts, team permissions or cloud service.

Browser live AI is **off**. Contextual evidence explanations read saved deterministic findings; they are not represented as model investigations. The preserved Nano orbital CLI integration is separate. Next is project-aware investigation against the saved revision and supported tools, followed by bounded model evaluation under the existing cumulative allowance. Broader 6D engineering, simulation and lifecycle capabilities remain in BUILD_PLAN.md and PRODUCT_FEATURES.md. October 21 remains a working snapshot checkpoint.
