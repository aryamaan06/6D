# 6D lifecycle foundation — implementation contract

Authorized for implementation October 14, 2026 after Arya organized the product and explicitly restarted building. The backend increment below is implemented and verified in the 115-test integrated suite, including precision regressions from independent review. The previous October 13 tasks were interrupted before application code was saved. October 21 is a checkpoint. This increment implements backend records, bounded engineering calculations, requirement review and revision impact; the new UI, arbitrary model execution, hardware verification and launch approval are not included. No live model spending was needed.

## Shared project format

JSON schema `sixd.project.v1`:

- `project_id`, `name`, `revision`, `description`: nonempty strings.
- `lifecycle_stage`: `design`, `simulation`, `physical_test` or `operation`; metadata only, not evidence that a stage has been verified.
- `inputs`: mapping of input IDs to `{value: finite number, unit: nonempty string, source: nonempty string}`. Boolean values are not numbers. No inferred units or conversions.
- `models`: list of `{id, type, inputs}`; `inputs` maps parameter names to project input IDs. Optional model description is metadata.
- `requirements`: list of `{id, title, model_id, metric, operator, limit_input, critical}`. Operators are `<=`, `>=`, `==`. Critical is a boolean. A requirement cannot be met by a missing model, result, unit mismatch or stale evidence.

IDs must be unique in each namespace, referenced inputs/models must exist, model mappings must be objects, non-finite values are rejected, and unknown fields are rejected except the optional model description. Require at least one model and one requirement. Allow unsupported model types to remain visible with `not_assessed` results; do not infer support from a domain name.

## Domain adapter interface

`sixd.engineering.evaluate_models(project)` returns a mapping keyed by model ID. Each result contains:

- `model_id`, `model_type`, `model_version`, `status` (`completed`, `not_assessed`, `invalid_inputs`), `metrics` mapping metric name to `{value, unit}`, `assumptions`, `not_assessed`, and `issues`.
- Only completed metrics from a maintained deterministic adapter may support a requirement comparison. These are calculated results, not proof of physical model validity.
- Initial types: `ideal_propulsion`, `static_cantilever`, `radiative_equilibrium`, `drag_load`. Unknown types abstain. Their bounded formulas and required parameters are documented by the adapter.
- Model definition, exact bound input records, adapter version and verification-source SHA-256 fingerprints are tied to each evidence receipt. Adapters expose `MODEL_VERSIONS`; existing orbital numerical audits retain their own report format for now.

## Lifecycle interface

`sixd.lifecycle.validate_project(project)` validates and returns a normalized deep copy.

`sixd.lifecycle.review_project(project, model_results)` validates adapter results, binds evidence to exact models/input records/versions, and evaluates requirements. The deterministic caller supplies fresh adapter results; this API is not a trust boundary for arbitrary externally asserted results. Each requirement gets `met`, `not_met` or `not_assessed`, with quantitative evidence where supported, applicability limits and a fingerprint of its model, bound inputs, adapter version and requirement definition including limit input. Validate model/result identity, versions, finite values, metric units and statuses. Unsupported results cannot become positive by having a numeric metric attached.

The `sixd.review.v1` review includes project metadata, immutable input/model/requirement snapshots, adapter versions, verification-source hashes, evidence, per-requirement status, `review_status` (`supported_requirements_met`, `requirements_not_met`, `incomplete`), unresolved requirements, failed requirements and explicit exclusions. `incomplete` takes precedence when any requirement is not assessed. Preserve failed findings separately even when review is incomplete. Always set `launch_authorization` to `false`; passing this bounded project review is not flight readiness.

`sixd.lifecycle.compare_reviews(old, new)` compares only the same project ID. It reports changed inputs/models/requirements, new/removed requirements, changed verification sources, requirements whose previous evidence needs rechecking, and requirements with unchanged evidence applicability. Changing a limit, units, provenance, model binding or version invalidates the relevant old evidence. Changing verification code conservatively invalidates all bound earlier requirements, even without a manual version bump. This is dependency impact from explicit bindings, not inferred physical interactions.

`sixd.lifecycle.verify_review(review)` checks deterministic fingerprints and report digest. Digests detect inconsistency, not an authenticated signature or proof of truth. Preserve old reports when writing new ones.

## Running the increment

`python run.py project-demo` produces three constructed baseline/revision/missing-evidence reviews without inference. `project-review PROJECT.json` accepts the documented structured manifest and computes fresh adapter results. `project-compare OLD.json NEW.json` compares saved reviews, and `project-verify REVIEW.json` checks internal consistency. Project manifests are limited to 2 MiB; saved review records to 16 MiB. Duplicate JSON keys and nonfinite numbers are rejected before evaluation. These inputs are records, not uploaded executable code.

## Ownership

- Lifecycle implementation: `src/sixd/lifecycle.py`, `tests/test_lifecycle.py`.
- Engineering adapters: `src/sixd/engineering.py`, `tests/test_engineering.py`.
- Existing verifier repairs: `src/sixd/kernel.py`, `tests/test_verification.py`.
- Lead integration: CLI, examples, reporting/output, integration tests, implementation documentation and final validation. No concurrent edits across ownership boundaries.

Use independent hand-worked reference/scaling cases, missing/invalid-input cases, unsupported models, critical evidence gaps and revision changes. Report current limitations. No generated illustration becomes an actual spacecraft requirement.
