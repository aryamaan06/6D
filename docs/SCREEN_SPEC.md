# 6D — first product journey and screen proposal

October 14, 2026. Prepared for Arya's review before UI implementation. This is a proposed experience, not a claim that these screens or all underlying capabilities already work. Keep one adaptable space-engineering product. The existing browser prototype stays unchanged until this proposal is reviewed.

## Purpose of the first journey

An engineer brings a design revision, its declared requirements and supported models. 6D computes what it can check, explains findings with evidence, preserves unresolved questions, and shows which earlier checks a revision affects. The first constructed journey demonstrates a supplied thrust/load change and a separately supplied heat change. It does not infer heat from thrust or simulate a complete spacecraft.

## Visual direction

Use Apple's clear hierarchy, careful spacing and focused explanations with Notion's calm, organized workspace. Original 6D design: warm light background, white content surfaces, near-black text, quiet borders and one restrained blue action color. Use system sans-serif typography, strong page titles and readable body text. No decorative space wallpaper, neon dashboards, invented scores or dense walls of technical labels.

Keep a compact left navigation and a single clear primary action per screen. Project name and revision remain visible. Evidence detail opens beside its finding so users retain context. On narrow screens, collapse navigation and stack the same content in reading order. Show status with words and icons as well as color. Full product breadth is represented through coverage and supported tools, not through buttons for unimplemented solvers.

## Proposed screens

| Screen | User's question | Content and primary action |
| --- | --- | --- |
| Project overview | What am I reviewing, and what needs attention? | Mission description, current revision, review scope, open requirements, latest evidence and outstanding questions. Action: Review this revision. |
| Design and requirements | What exactly do I provide, and what will 6D check? | Planned intake: import a supported project JSON file or start from an explicit reference template and edit its form fields. Show parameters, sources, exact SI unit labels, model mappings, assumptions and requirement comparisons/limits before confirmation. Changes create a new review baseline. Action after intake: Confirm review inputs. |
| Investigation | What is happening, and why? | Visible provider mode, selected supported tool, reason for its selection, actual result and next step. Separate agent failure from numerical findings. Show spend reservation/usage when available. Action: Start review, then cancel where cancellation can honestly be honored. |
| Evidence and findings | Which requirements are met, which are not met, and which were not assessed? | Separate sections for assessed requirements met, calculated requirements not met, and requirements not assessed. Calculated rows show value, unit, comparison operator and declared limit. Unassessed rows show the reason and missing evidence or unsupported capability. Each section links to assumptions and source/version receipts. Action: Open evidence. |
| Changes | What does this revision affect? | Compare two baselines, show changed values/limits/model/source bindings, affected earlier evidence and unaffected applicability. Explain that explicit dependency links do not predict new physics. Action: Review affected checks. |
| Report | What can I share or reproduce? | Reviewed configuration, assessed requirements, failures, unresolved questions, assumptions, model/source versions and reproduction instructions. Action: Export report. |

Physical-test and operational evidence will enter this same journey as validated integrations become available. They do not need separate unrelated products. An unsupported upload format is explained clearly and never silently converted into a completed engineering review.

## Intake: what works now and what the new interface will offer

The current backend accepts a **`sixd.project.v1` JSON manifest through the CLI**: `run.py project-review PATH`. Its built-in reference scenarios run through `run.py project-demo`. The existing browser prototype does not import these project manifests or provide the proposed intake forms. The buttons and forms below are a specification for implementation, not current controls.

Proposed intake guidance: **"Import project JSON or start from a reference template. Provide parameters, sources, requirement limits and explicit SI units."** Use two clearly named choices: **Import project JSON** and **Start from a reference template**. A template identifies its constructed provenance, supported models and assumptions; it does not supply certified design limits. Form edits produce the same supported manifest and are reviewed before a run.

A manifest contains the project identity/revision and description, named numerical inputs with units and sources, explicit model-to-input mappings, and requirements with a model metric, comparison operator and limit input. Accept only the supported schema and exact unit labels; do not silently convert arbitrary files or infer missing limits. Explain an invalid field where it occurs. If a domain is unsupported, retain its declared requirement as not assessed instead of suggesting it passed.

## Planned capability: simulation and playback

Simulation/playback remains part of the full 6D product plan, specified in `docs/SIMULATION_PLAYBACK.md`, but is **not implemented**. It is omitted from the first active navigation and primary-action flow. If the proposal shows a roadmap entry, label it **"Planned capability — Simulation and playback"** and provide an explanation only. Do not show an enabled Run simulation or Replay control until the corresponding supported runner and run-data viewer work and pass their acceptance checks.

The future capability will link plots and suitable 2D/3D playback to actual model runs, project revisions, conditions, units/reference frames and evidence. Supported baseline/scenario comparisons will show what changed. Scalar-only or unsupported results will explain their coverage rather than inventing motion. Once implemented, this can contribute evidence during investigation and be inspected after review; a positive review is not required to examine a predicted failure. Geometry/motion sources must be explicit, and illustrative animation must be labelled separately from calculated simulation.

## Language and evidence states

- **Declared requirements met:** all requirements in this review have supported evidence meeting their supplied limits. Always pair this with scope and model assumptions.
- **Requirement not met:** place it in **Calculated requirements not met**. Show the actual calculated value, unit, declared comparison (`<=`, `>=` or `==`), limit, assumptions and evidence. A negative margin is one possible unmet requirement, not the universal failure criterion or a broken-app message.
- **Requirement not assessed:** place it in **Requirements not assessed**. Show the specific reason and what model, input, mapping or evidence is needed. Unsupported control analysis and missing or incompatible evidence are limitations of this review; they are not calculated vehicle defects. Do not manufacture a numerical result for these rows.
- **Review incomplete:** identify outstanding unassessed requirements. Preserve calculated unmet requirements in their separate section even when the overall review is incomplete.
- **Invalid input:** identify the specific field, unit or reference to correct; retain the user's work.
- **Investigation interrupted or failed:** retain completed evidence, label the agent state separately, and do not imply the agent finished successfully.
- **Earlier evidence needs rechecking:** explain the changed dependency; preserve the old receipt as history.
- **Live / scripted / deterministic:** show the actual execution mode. A scripted sequence must never appear as a Nemotron conversation.

Avoid an overall "rocket is perfect", "safe to launch" or percentage-confidence badge. Readiness recommendations later require an explicitly defined review and adequate evidence; these screens do not confer launch authority.

## First walkthrough for Arya

1. Understand the project and its declared review scope.
2. Review the inputs, assumptions and limits.
3. Watch supported calculations/investigation run.
4. Read the thermal failure in the changed constructed revision and inspect its evidence.
5. See which earlier requirements were affected, then add an unsupported control requirement and understand why the review remains incomplete.
6. Export the evidence with the unresolved list visible.

Review the labels and reading order: flag anything you cannot understand without an explanation, and identify which screen feels too crowded. Apple/Notion is the agreed direction; screenshots are optional. This review concerns the product experience, not Arya's ability to validate spacecraft equations.

## UI acceptance gate

A first-time reviewer can complete the supported flow, distinguish a failure from missing evidence, find assumptions and source receipts, and compare revisions without losing context. Keyboard navigation, contrast, mobile layout, loading/empty/error states and truthful provider status are verified before describing the new interface as complete.
