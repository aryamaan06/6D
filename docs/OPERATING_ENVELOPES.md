# Sampled operating-envelope studies

Delivered locally October 23, 2026 · build `395f0632f981`.

Open http://127.0.0.1:8768/, refresh, and choose **Envelope studies** in the top
toolbar. This extends the existing hypothetical scenario engine; it adds no
physics family and does not change canonical project findings.

## Use the workflow

1. Select the latest saved revision of a project and run its baseline checks.
   The envelope page offers **Run baseline checks** when no current run exists.
2. Enter a study name and the source/justification for the proposed ranges.
3. Choose an eligible model input. Enter its minimum, maximum and sampled-point
   count. Add up to two more axes if needed. Units come from the saved input.
4. Click **Preview exact grid**. Review every generated combination and the
   selected baseline. Preview executes no model. Editing the form invalidates it.
5. Explicitly **Run and save** the reviewed grid. Inspect the per-requirement
   summary, select a requirement, and open a sampled case for its exact inputs,
   findings, model reuse, assumptions and exclusions.
6. Export/print the study or open the full project report. Combined review JSON
   captures complete retained study evidence in the same read snapshot.

For a constructed project with the drag-load model, two illustrative axes are
`density` from 0.01 to 0.03 kg/m³ (two points) and `relative_speed` from 100 to
200 m/s (two points). This gives four sampled combinations. These are workflow
examples, not recommended flight conditions or engineering requirements.

## What the result means

Every requirement retains its own criterion and unit. For `<=` and `>=`, the
worst observed margin is the smallest signed margin among assessed cases. For
`==`, it is the largest absolute difference from the exact target. All exact ties
are listed. Margins from different requirements or units are never ranked.

The summary separately records met, not-met and not-assessed counts, unresolved
case identities and any worst observed finite margin. A violation and unresolved
cases may coexist. Overflowing/unavailable margins cannot create an all-sampled-
met result. Case details retain the maintained adapter's original reason for an
invalid or numerically unsupported calculation.

**All sampled cases meet criterion** applies only to those explicit points and
the recorded models. It establishes neither behavior between points nor a safe
continuous envelope. No interpolation, optimization, probability distribution or
global worst-case search is performed. Plots show discrete case observations;
case order is not a physical time axis.

## Scope, retention and limits

- One to three distinct axes, two to nine equally spaced points on each, no more
  than sixteen Cartesian combinations. Exact endpoints and generated samples are
  recorded. Finite, distinct, browser-representable values are required.
- Requirement-limit inputs, numerical tolerances, integration step counts and
  assessment-window settings are frozen. Linked-only overridden or unsupported
  parameter roles are not offered as independent axes. Shared frozen input IDs
  remain excluded even when another model also uses that input.
- Existing computation bounds apply: up to 64 models and a conservative total of
  32,768 retained dynamic samples across the baseline and combinations. Receipt
  size is bounded to 32 MiB. The app does not silently reduce resolution to fit.
- Studies are append-only hypothetical records. No saved project revision/run is
  created by a study. A changed baseline, latest revision or source context blocks
  stale writes or marks existing evidence historical. Reads verify retained
  evidence without invoking a solver.
- Study list history is the latest twenty scenario records, including legacy
  scenarios. The report snapshot independently includes up to twenty whole grid
  studies within 32 MiB, with explicit omissions. Individual exports remain
  available; the full combined review retains its existing 64 MiB bound.
- Legacy sweep/alternative receipts keep their original schema, disclosures and
  findings. New grid receipts use `sixd.envelope-study.v1`. Future changes must
  preserve schema-specific interpretation of retained evidence.

No API key is needed. All calculations remain within the existing bounded model
assumptions; source ranges and physical applicability are user declarations.
Unsigned consistency digests do not authenticate approval or authorize launch.
