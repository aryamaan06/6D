# Scalar test-data import and prediction comparison

October 18, 2026. This increment records supplied scalar observations against the exact saved design prediction. It does not authenticate physical testing or change canonical engineering findings.

## Use in 6D

1. Open http://127.0.0.1:8768/ and select the saved revision matching the tested configuration. Save or discard any draft. Use **Run baseline checks** if prompted.
2. Choose **Test data** in the toolbar. Enter a comparison name, source/provenance and explicit data origin: supplied measurements or synthetic/constructed data.
3. Describe what the measured scalars represent and the test conditions. Declare whether their observable, aggregation and model conditions match the saved baseline. This declaration is recorded as **unverified**. A transient temperature is not automatically an equilibrium temperature; an instantaneous orbital radius is not a minimum over the model's sampled window.
4. Upload a UTF-8 CSV, or enter a source filename/label and paste CSV text. Choose **Read headers / preview CSV**.
5. Map columns explicitly to measurement ID, requirement ID, measured value and unit. Optionally map a nonnegative absolute agreement tolerance in that same unit. Choose **Preview current CSV and mappings** again. Inspect raw cells, normalized values and row issues. Changed CSV/mappings require a fresh preview before saving.
6. Choose **Save test comparison**. Read the two separate outcomes per row, inspect the scalar plot, original CSV, frozen baseline inputs/model bindings and exclusions, then export JSON or print/save PDF.

Opening history performs no physics or inference. A stale baseline can be reloaded through the page action without discarding its in-memory CSV form. Forms are not persisted in browser storage; explicitly refreshing/closing the browser can discard unsaved form entries. Saved comparisons survive application/server restarts.

## What each outcome means

**Measurement meets requirement:** the supplied normalized measurement is compared with the frozen requirement's exact operator and limit. `met`, `not_met` and `not_assessed` are separate states. Exact `==` receives no guessed tolerance.

**Prediction agrees within tolerance:** the absolute difference between the supplied measurement and saved prediction is compared with the row's explicit nonnegative absolute tolerance. Outcomes are `within_tolerance`, `outside_tolerance` and `not_assessed`. Signed difference is measured minus predicted. A missing/invalid tolerance leaves this outcome unassessed while an otherwise valid measured requirement can still be checked. Zero tolerance is explicit and allowed. An overflowing difference is not printed as infinity; it is labelled outside every supported finite tolerance.

These outcomes can disagree. A measurement may violate a requirement while agreeing with a prediction. Both prediction and measurement may violate the requirement while agreeing closely with each other. Agreement does not establish model validation, and criterion satisfaction does not establish test authenticity or launch readiness.

The first comparison implementation requires a supported, assessed baseline prediction/criterion, exact matching units, nonempty measurement-definition/conditions text and a declared match. Unknown/different conditions, unsupported requirements or unassessed baseline results remain gaps. Imports cannot create a missing solver, close unsupported coverage, change a canonical verdict or calibrate a model automatically. No conversion, time-series alignment, probability or confidence interval is inferred.

## CSV and provenance

The parser supports a UTF-8 CSV up to 1 MiB, 200 data records, 32 columns and 4096 characters per field. Headers must be distinct/nonempty; every record must have the header's field count. Quoted commas and newlines are supported. Preview row numbers count logical CSV records (header is record 1), not physical text lines inside quoted fields.

Missing values never become zero. Invalid/nonfinite numbers, duplicated measurement IDs and unknown mappings remain explicit gaps. Negative tolerances are invalid. Integer tokens outside the browser's exact safe-integer range remain gaps instead of being silently rounded; unsafe integer prediction/criterion operands also cannot support a displayed comparison. Decimal/scientific values use finite binary floating point rather than arbitrary decimal precision. Original numeric text remains in the supplied CSV.

File upload preserves the decoded UTF-8 text, BOM and Windows CRLF line endings through previews and metadata/mapping edits. Only an intentional CSV text edit changes that submitted source. The saved CSV SHA-256 covers the exact submitted UTF-8 text, including explicit edits. Formula-like cells remain inert strings: they are neither evaluated nor exported as an executable spreadsheet. All preview/report text is escaped.

Every immutable comparison retains the submitted CSV/hash and mapping, data-origin/source/condition declarations, exact project/revision and baseline run/review digests, row quality gaps, both derived outcomes and source hashes. Read-time verification checks those stored derivations without executing adapters or models. Digests are unsigned consistency checks, not authentication or physical proof. New revisions, a replaced baseline run or changed installed comparison sources label prior records historical.

## Optional constructed walkthrough

Two files in the project's `examples` folder provide a labelled synthetic example:

- `test-data-reference.project.json`: import this as a new project, inspect its inputs and run baseline checks.
- `test-data-synthetic.csv`: upload this on Test data, map its five named columns and choose synthetic origin. Describe the same steady drag-force definition with density 1.2 kg/m³, speed 50 m/s, coefficient 0.8 and area 0.25 m². The independent hand reference is 300 N. The observations are constructed numbers, not physical tests.

The fixture demonstrates requirement failure despite prediction agreement, both criteria failing despite agreement, an exact tolerance boundary, an exceeded boundary, a unit mismatch and a missing tolerance. These are software acceptance examples, not measured validation of a space vehicle.

## Implementation boundary

The additional `test_comparisons` SQLite table is append-only through the app. Canonical project revisions/runs, scenario studies, simulation evidence, Assistant configuration and allowance ledger are preserved. The API surface is `POST /api/test-data/preview`, `GET/POST /api/test-comparisons`, `GET /api/test-comparisons/<id>` and `GET /api/test-comparison-export`. Existing loopback Host/Origin, strict JSON/body-size and runtime guards apply. The v1 read/derivation contract must be preserved or explicitly versioned when adding future formats.

Automatic measurement extraction, instrument integration, independent condition verification, uncertainty propagation, calibration, time histories, qualification/certification and general physical-test acceptance remain later work. This milestone requires no Nebius connection or paid request.
