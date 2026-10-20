# Scenario comparison and sensitivity

October 18, 2026. This increment explores explicit hypothetical inputs with the existing maintained calculators. It adds no new physics or live model calls.

## Use in 6D

1. Open http://127.0.0.1:8768/ and select a saved project revision. If necessary, run its baseline checks first. Save or discard any draft.
2. Choose **Scenarios** in the workspace toolbar.
3. Give the study a name and state the source or justification for its hypothetical values.
4. For **Single-input sweep**, select an existing input and enter 2–16 distinct decimal values separated by commas. The baseline unit is retained. The form identifies model-parameter, requirement-limit and unreferenced roles. No numeric defaults are supplied.
5. For **Named alternatives**, give each alternative a name and add its explicit input changes. Up to 16 cases and eight changes per case are supported.
6. Choose **Run and save study**. Select a requirement to compare numeric evidence, each case's own criterion, signed margin or exact-target difference, and baseline-to-case findings.
7. Inspect the case evidence, assumptions, exclusions, execution/reuse and next checks. Open earlier saved studies without recalculation. Export the full JSON or print the report to PDF.

New cases are hypothetical configurations. The baseline revision, canonical run and project verdicts are unchanged. A study is not automatically promoted to a saved revision. A justified change can be entered later through the existing draft/revision workflow.

## Meaning of the results

- A sweep calculates only the supplied values. Points are not an interpolated prediction, guaranteed safe range, optimization or continuous envelope.
- Only declared bindings propagate changes. A model parameter change recalculates affected models; an unchanged model reuses the exact baseline evidence and original execution provenance. A requirement-limit change can change the finding without changing any physical calculation. No hidden physical coupling is inferred.
- `met`, `not_met` and `not_assessed` remain distinct. Invalid physical inputs and unsupported models create evidence gaps, not fabricated vehicle failures. No whole-mission pass or launch authorization is issued.
- For `<=`, signed margin is limit minus result. For `>=`, it is result minus limit. Nonnegative meets those comparisons. For exact `==`, the reported quantity is absolute difference, and only zero meets the exact target; no tolerance is inferred. Nonfinite differences are omitted with an explanation. Units remain explicit; unlike margins are never ranked together.
- Orbital cases retain real saved 3D samples from the existing bounded two-body adapter. Orbital extrema apply only to those samples and the declared duration. Scenario study receipts are distinct from project playback and standalone simulation receipts; this increment compares their scalar findings rather than adding scenario playback controls.
- The result plot uses stored metric/criterion points and a separately marked baseline result. Unsupported or invalid findings have no fabricated plot point. Exact values remain available in tables and JSON.

This is bounded deterministic sensitivity, not quantified uncertainty, failure probability, an optimizer or a new coupled launch/landing solver. Existing model assumptions and physical-validation gaps continue to apply.

## Storage and verification

`scenario_studies` is a new append-only SQLite table. Each record binds an immutable baseline run and its digest, exact revision/project, normalized explicit specification, input sources and units, per-case reviews, model execution/reuse origins, calculation-source hashes and limitations. Read-time checks verify record consistency and baseline binding without executing models. Unsigned digests do not establish authenticity or prove physical truth.

Studies are labelled historical if the selected revision, latest current baseline run or installed sources differ. An old study cannot be opened in a revision earlier than its baseline. Source/runtime changes block new calculations until restart and a current baseline review. Concurrent studies are refused. Preflight bounds are 16 cases, 64 models and 32,768 retained orbital samples across baseline/cases; receipt size is limited to 32 MiB. Use fewer explicit cases when needed; the application does not silently reduce resolution.

The HTTP surface is `GET/POST /api/scenarios`, `GET /api/scenarios/<study_id>` and `GET /api/scenario-export`. Existing loopback Host/Origin, strict JSON/body-size and runtime guards apply. The UI blocks new studies while a draft is active. In-flight requests cannot overwrite another selected project/revision's view. Saved records can still be inspected while a draft exists.

The v1 evidence/verification contract must remain readable when extending future study formats. Changes to its semantics need an explicit schema/version path. No provider connection, selection, spending limit or live model policy changes here.
