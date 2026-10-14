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
| Design and requirements | What exactly will 6D check? | Structured inputs with units/sources, explicit model mappings, assumptions, requirement limits and supported/unresolved coverage. Changes create a new review baseline. Action: Confirm review inputs. |
| Investigation | What is happening, and why? | Visible provider mode, selected supported tool, reason for its selection, actual result and next step. Separate agent failure from numerical findings. Show spend reservation/usage when available. Action: Start review, then cancel where cancellation can honestly be honored. |
| Evidence and findings | What passed, what failed, and why? | Requirement summaries with calculated value versus limit, model applicability, source/version receipt and detail on demand. Keep unmet and unresolved findings visible together. Action: Open evidence. |
| Simulation and playback | How is this configuration predicted to behave? | Planned model-linked plots and 2D/3D playback with a timeline, stated conditions, units/reference frames, evidence links and supported baseline/scenario comparisons. Available only when suitable run data exist; scalar-only or unsupported results show a clear coverage explanation. Action: Run supported simulation or replay a recorded run. |
| Changes | What does this revision affect? | Compare two baselines, show changed values/limits/model/source bindings, affected earlier evidence and unaffected applicability. Explain that explicit dependency links do not predict new physics. Action: Review affected checks. |
| Report | What can I share or reproduce? | Reviewed configuration, assessed requirements, failures, unresolved questions, assumptions, model/source versions and reproduction instructions. Action: Export report. |

Physical-test and operational evidence will enter this same journey as validated integrations become available. They do not need separate unrelated products. An unsupported upload format is explained clearly and never silently converted into a completed engineering review.

Simulation/playback was added to the product proposal October 14 and is not currently implemented. It is available during supported investigation as well as after review; failed or incomplete reviews can have useful simulated evidence. A positive review is not required to inspect a predicted failure. Geometry/motion sources are explicit, and illustrative animation is labelled separately from calculated simulation.

## Language and evidence states

- **Declared requirements met:** all requirements in this review have supported evidence meeting their supplied limits. Always pair this with scope and model assumptions.
- **Requirement not met:** show the actual calculated value, limit, unit and evidence. A negative engineering margin is a finding, not a broken-app message.
- **Review incomplete:** identify missing or unsupported evidence. Preserve any existing failures alongside this state.
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
