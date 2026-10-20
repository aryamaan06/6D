# 6D workspace design review

October 15, 2026. This guide accompanies the authorized design milestone. It describes what to review; it is not a receipt that the prototype has passed review or that the new application UI has shipped.

## Artifact and scope

The repository-owned inline preview is `design/workspace-preview.fragment.html`. A browser inspection wrapper is generated at ignored `work/workspace-preview.html`. The preview can also be shown in this existing chat. No new chat, account, credential or model setup is required.

The preview explores Flow-style connected engineering work, Apple's visual hierarchy/finish and Notion's organized workspace. It is original 6D design. Illustrative project records, assistant explanations and captured-result replay are visibly labelled. Its fixed reference interaction is not a live investigation or general simulation engine.

The current application UI, engineering backend and installed live Nano configuration remain unchanged by this artifact. No paid inference or external integration is needed for the design walkthrough. Offline reference calculations can supply snapshots; clicking their replay does not execute the backend again.

## Walkthrough: Thermal change review

| Step | Action | What to assess |
| --- | --- | --- |
| 1 | Select Thermal in the system hierarchy. | The project, baseline revision and selected system are clear. Input, model, requirement and evidence connections have understandable meaning. |
| 2 | Inspect a linked requirement/evidence record. | Inspector exposes units, assumptions, limit and source without obscuring the workspace. |
| 3 | Switch Canvas, Table and Reader. | These are views of the same selected system and revision, not separate datasets or unrelated destination pages. |
| 4 | Select Investigate on the temperature requirement. | Assistant opens with a pinned project/revision/requirement and visible assumptions, limit and evidence. Its response is labelled illustrative. |
| 5 | Stage the reference heat change from 200 W to 600 W; the limit is 320 K. | Draft editing distinguishes baseline and unsaved changes. Invalid entries receive field-specific feedback. |
| 6 | Preview affected dependencies. | Changed inputs and evidence needing rechecking are highlighted. The preview does not claim a newly calculated temperature or an effect on unrelated disciplines. |
| 7 | Save revision 2 and choose Rerun affected checks. | The prototype identifies captured reference-result replay, preserves baseline evidence and shows the new revision's result separately. |
| 8 | Open Changes and Report. | Revision differences, a calculated unmet requirement and a separate unassessed control requirement are understandable. Return to the selected system is straightforward. |

The reference is constructed, uses a bounded steady radiative model and changes supplied heat only. It does not represent a verified spacecraft, aerodynamic heating, coupled propulsion/thermal behavior or mission playback. Sample values and snapshots are reference material, not permanent 6D design requirements.

## Review checklist

- The first screen reads as a useful engineering workspace with clear hierarchy, restrained colors and readable spacing.
- Sidebar hierarchy and revision switching establish scope; Canvas/Table/Reader preserve it.
- Requirements, model inputs and evidence remain discoverable through both the graph and a non-canvas view.
- Inspector and Assistant preserve context; Investigate is explicit rather than an unexplained panel replacement.
- Draft changes, affected dependencies, saved revisions and rerun evidence are distinguishable states.
- Met, not met, not assessed and evidence needing rechecking have different labels and explanations.
- Charts and reports identify their source and use appropriate units and scales.
- Pan/zoom and keyboard actions do not trap focus or lose selection; narrow layouts retain a usable path to the tree and context panel.
- Empty, error and loading presentations provide useful information and recovery, with no simulated activity presented as a real agent run.
- Sample data, fixed interactions and offline replay remain visible enough that a reviewer cannot mistake the preview for the working application.

## Recording feedback

Record the selected view, attempted action, confusing behavior and expected outcome. Prioritize a broken journey or lost context before cosmetic refinements. Application UI replacement follows review of this artifact and its interactions. The implementation lead records validation receipts and known prototype limitations after inspection; none are claimed by this guide alone.

## Recorded development validation — October 15

The isolated preview passed 12 automated browser walkthrough checks in headless Chrome: baseline reference evidence; synchronized views/selection; keyboard view switching; draft impact; stale evidence after saving; recorded replay and scoped explanation; separate control gap; report export; invalid draft preservation; draft-limit consistency; refusal to invent results for an uncaptured input; and desktop/tablet/narrow layout behavior. The final run recorded zero runtime errors and zero provider/API requests. This is development validation, not founder acceptance or independent engineering qualification.

Inspection widths were 1440, 1024, 736, 390 and 320 pixels. Desktop and narrow screenshots were inspected. At narrow widths the dependency items reflow into a readable list, with the Inspector below; the system tree remains available. A read-only implementation review found no remaining delivery blocker after the evidence-state and dependency fixes.

The local receipt is ignored work/workspace-preview-validation.json, with screenshots in work/workspace-desktop.png, work/workspace-wide.png and work/workspace-mobile.png. The offline fixture generator verified its review records and reproduced byte-identical reference data. The existing application source is unchanged; the 237-test backend suite was not rerun for this isolated design artifact.

Known prototype boundaries: no shared project storage or backend rerun; the assistant is scripted; the captured thermal grid is limited; local draft/revision behavior is not team branching/approval. The report export exposes selectable JSON because the conversation sandbox can prohibit downloads. Simulation playback and broad file ingestion are not included in this design milestone.
