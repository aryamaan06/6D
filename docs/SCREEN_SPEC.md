> Planning/development reference with historical status notes. See the [current project record](PROJECT_RECORD.md) and [delivered/pending A–F scope](HACKATHON_BUILD_SCOPE.md). Design intent and the broader vision remain useful; dated status, model choices and task sequences are not current delivery claims.

# 6D — connected engineering workspace specification

October 19 delivered: Calculation chains is a scoped workspace view with a dependency graph, exact-unit connection editor and saved scalar provenance. It uses the shared project draft/revision rather than a separate configuration. Table/Inspector model edits preserve explicit links; Changes previews transitive dependencies. Existing Canvas/Table/Reader, reports and other discipline pages remain available. See CALCULATION_CHAINS_ACCEPTANCE.md.

October 17 authoring interaction: New project saves an explicit empty R1; Author project edits shared draft metadata, inputs, model bindings and requirements. Record dialogs require explicit supplied values/sources and preserve stable IDs. Setup validation is read-only and distinguishes configuration readiness from engineering findings. Definition additions/removals are shown in Changes. Existing Canvas/Table/Inspector and Simulation remain connected. See PROJECT_AUTHORING.md.

October 17 implemented interaction: Simulation has Project evidence and Exploratory scenarios modes. Project trajectories are opened from exact model/requirement/report receipts, show their canonical findings, and return to existing Table/Inspector draft editing or scoped investigations. New orbital template onboarding and Run affected checks use the shared revision workflow. Historical/draft findings cannot initiate an investigation for a different current review. See ORBITAL_WORKFLOW.md.

Updated October 15, 2026. Arya authorized the workspace design milestone. This specification describes the intended application and its separate review prototype, not shipped application features. The existing orbital browser, engineering backend and verified Nano integration remain intact.

## Design direction

Use Flow Engineering as the interaction/workflow reference: persistent project hierarchy, linked engineering objects, canvas/table/reader views, contextual assistant and revision review. Combine this with Apple's typography, spacing, hierarchy and finish, and Notion's clear workspace organization. Create an original 6D identity.

Use light neutral backgrounds, white content surfaces, near-black text, quiet borders, readable system typography and restrained blue actions. Use category colors sparingly and pair status colors with words/icons. Graph connections, charts and diagrams convey project meaning. Avoid decorative dashboards, fabricated scores or dense text walls.

## Workspace layout

| Region | Content and behavior |
| --- | --- |
| Left navigation | Project switcher, revision switcher, search and expandable system/subsystem hierarchy. Selecting a system establishes the scope for every main view. Do not create separate primary destinations for systems, requirements and evidence. |
| Top context bar | Project/system breadcrumbs, selected revision, Canvas / Table / Reader modes and context-relevant search/filter/actions. Changes and Report are secondary project controls, not competing object hierarchies. |
| Main work area | The same selected system and linked records in the chosen view. Canvas reveals explicit relationships; Table supports precise inspection and draft editing; Reader explains those records and evidence. Preserve selection, revision and draft while switching modes. |
| Right contextual panel | Persistent item header pins project, revision and selected record. Inspector and Assistant are explicit tabs within that context. Switching tabs retains the record, assumptions, limits and evidence links. |
| Status/history | Actual run state, unresolved requirements, saved evidence and prior revisions. Show active model/mode and cost information in an appropriate details area rather than overwhelming engineering content. |

October 17: Simulation is now an active secondary project view for bounded 3D orbital runs. The project/revision sidebar stays visible; its wider viewer replaces the requirement Inspector temporarily. It has independently supplied scenario inputs, actual saved run selectors, compatible comparison, exact-sample playback, 3D and 2D projections, numerical histories and source disclosures. Existing requirement findings are unaffected. Broader simulation actions become active only when their supported model and viewer work. Integrations show actual connection state. No dead buttons or fictional agents imply unavailable functionality.

Canvas supports selection, pan, zoom and fit-to-view. Connections have meaningful labels and direction. The same records are accessible through Table and Reader. Changes and Report open secondary review surfaces and retain a return path to the selected system. Changing revision updates the selected records and evidence together; prior evidence never silently covers a new configuration.

## Shared information model

Proposed first connected records: project, system/subsystem, input, model, requirement, run/evidence and finding. Explicit typed links describe containment, input use, requirement verification and recorded dependencies. Interfaces and source/document records expand as their supported intake is implemented.

Canvas, table and reader reference the same stable IDs and revision. Renaming or editing an item is reflected across views. Layout position does not change engineering data. Display connection types and provenance; a hierarchy link does not establish physical coupling.

Current sixd.project.v1 is strict and lacks a system hierarchy/general relationships. Plan explicit compatibility or migration; do not silently add fields to old receipts or break reproduction.

## Draft editing and revision staging

1. Choose Edit draft from Table or Inspector. Show the saved baseline revision and an unsaved-draft indicator.
2. Edit supported values or requirement limits in place, retaining explicit units and source information. Keep the baseline immutable.
3. Validate the edited field. Preserve invalid text, explain the specific error and block saving or rerunning an invalid draft.
4. Preview affected dependencies. Highlight the changed record and linked models, requirements and evidence needing rechecking. Explain which dependency produced each highlight. Retain previous measurements as earlier evidence; preview does not calculate new physics.
5. Review field differences and explicitly save a new revision. Offer discard before saving; cancellation preserves the baseline.
6. Rerun affected checks for the saved revision. Only applicable supported checks execute. Missing models or inputs remain not assessed.
7. Compare baseline and new revision: changed fields, affected dependencies and resulting evidence. Distinguish a pending rerun from a completed calculation and preserve the old receipt.

The design prototype may rehearse this loop with a fixed reference edit and captured snapshots. Label replay clearly. A staged preview must not imply arbitrary values have been calculated by a connected solver.

## Investigation handoff

Every requirement card and Table row offers an explicit Investigate action. It selects the record and opens Assistant with project ID, saved revision, requirement ID, assumptions, units, bounds, linked model and evidence already in scope. The context header stays visible beside the conversation.

Opening Inspector or following evidence does not discard the investigation context. If the user selects a different system or revision, keep the investigation's pinned context visible and require an explicit new investigation or handoff before applying its results elsewhere. An unsupported requirement opens with its actual missing-model/input explanation.

The working application shows actual tool activity and distinguishes deterministic, scripted and live inference. The prototype uses an explicitly illustrative assistant explanation; no live request or hidden agent execution occurs.

## Named walkthrough: Thermal change review

1. Open the clearly labelled constructed reference project or import a supported project JSON.
2. Select its thermal subsystem in the project tree. The canvas focuses its input, model, requirement and evidence relationships.
3. Switch between table and reader; preserve selection and revision.
4. Inspect supplied input sources, units, assumptions and requirement limits.
5. Inspect the baseline heat input of 200 W and 320 K temperature limit. Select Investigate on the temperature requirement; retain its project/revision/requirement context in Assistant.
6. Enter draft editing through Table or Inspector and stage the reference heat change to 600 W. Preview the thermal model, requirement and evidence needing rechecking, without inferring changes in other disciplines.
7. Save revision 2 after reviewing the field changes. The saved baseline and its evidence remain available.
8. Rerun the affected supported check, inspect its result and compare revisions. In the design prototype this action replays a labelled, captured deterministic reference snapshot rather than calling the backend.
9. Retain an unsupported control requirement as not assessed; a missing control model cannot become a passing result.
10. Export a report that matches the selected revision and preserves unresolved questions.

The design walkthrough changes the supplied thermal input only. It does not infer heat from thrust, simulate a coupled spacecraft or predict its trajectory. Supporting reference snapshots may be computed offline with the existing kernel; clicking replay is not a new backend run. Sample values are reference material, not permanent product requirements.

## Intake

The implemented backend accepts supported project JSON via CLI. Proposed browser controls are Import project JSON and Start from a reference template, followed by understandable forms with explicit units, sources, mappings, limits and assumptions.

This design milestone does not implement upload or arbitrary file extraction. Any reference-project action opens the declared illustrative records.

Preserve invalid work and explain the specific field. Unsupported file formats are explained clearly. Future PDF/CAD extraction proposes source-linked records for review before engineering use; it does not silently certify an uploaded drawing.

## Visual evidence and knowledge tools

| View/tool | Intended purpose | Evidence rule |
| --- | --- | --- |
| System/dependency map | Explore systems, requirements, models and change consequences | Render actual records/links; distinguish declared dependency from calculated physical effect. |
| Data/margin tables and charts | Inspect values, units, limits, trends and revision differences | Use recorded results; identify source/run and scale. Static results do not imply time histories. |
| Findings/report reader | Understand what meets requirements, what fails and what is unresolved | Exact source links and reproducible calculation evidence. |
| Explanatory mind maps/infographics | Explain project structure and findings at an appropriate depth | Distinguish sourced facts from explanatory simplification. |
| Optional understanding quizzes | Help a user check understanding of the supplied project or report | Not a compliance test or evidence of design correctness. |
| Simulation/playback | Inspect predicted behavior from a supported time-history model/import | Exact run/revision, conditions, units/frames and traceable motion; follow SIMULATION_PLAYBACK.md. |

## Required states

- Requirement met: evidence meets its declared criterion within stated scope.
- Requirement not met: show actual value, unit, operator, limit and evidence.
- Requirement not assessed: show missing input, unsupported model or incompatible evidence; never label this a calculated defect.
- Review incomplete: preserve unmet findings while showing remaining unassessed requirements.
- Earlier evidence needs rechecking: show changed dependency and retain history.
- Agent failed/interrupted: retain completed calculations; report failure separately.
- Invalid input/no data/no results: explain the next meaningful action.
- Proposed changes: inspect differences before adoption; preserve the baseline.
- Draft invalid/unsaved/saved: distinguish saved configuration from proposed values; show pending versus completed rerun evidence.
- Actual provider/mode: live, scripted or deterministic; no simulated progress pretending to be real tool work.

No blanket rocket-perfect or launch-authorization badge. Later readiness recommendations require explicitly defined criteria and adequate evidence.

## Reviewable visual prototype — design milestone

Repository-owned inline source: `design/workspace-preview.fragment.html`. A browser inspection wrapper is generated under ignored `work/workspace-preview.html`. Review the annotated clickable layout for:

1. System canvas plus contextual panel.
2. The same selection in table/reader.
3. A real-data-shaped unmet finding and separate unresolved requirement.
4. Revision comparison and report.
5. Empty/loading/error and a narrow-screen layout.

Clearly identify illustrative content, fixed interactions and captured-result replay. The preview is a standalone offline artifact, not a replacement for the current application or a validated mission run. It must not request a key, call a provider or write production revisions. Arya reviews it against the supplied Flow/Notion references and Apple quality direction before application UI replacement. `WORKSPACE_DESIGN_REVIEW.md` gives the walkthrough/checklist; verification receipts are reported separately.

## Acceptance

A first-time user completes the supported journey, follows a finding to its source, understands missing evidence and compares revisions without losing context. Selection/data remain consistent across views. Verify keyboard use, contrast, graph navigation, useful density and loading/error behavior. Judge finish through the complete walkthrough, not isolated attractive screenshots.

Primary workflow reference reviewed October 15: https://www.flowengineering.com/product/systems-graph . This is design research, not a claim that 6D currently matches Flow's capabilities.
