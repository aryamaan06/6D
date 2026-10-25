# Find your way around 6D

Build 1 navigation and typography, authorized October 25, 2026. This guide describes the existing engineering capabilities through a new hierarchy; it does not add new physics or enable additional AI models.

## Start with a project

Open http://127.0.0.1:8768/ and refresh. The **Projects** screen lists saved projects and offers the rocket example, an empty project or import/templates. Opening a saved project displays its **Overview**. The project and saved-revision selectors remain in the sidebar inside that project. **All projects** or the 6D brand returns to the project list.

## Choose one work area

| Work area | Existing destinations |
| --- | --- |
| Overview | Current saved review, rocket reference steps, findings and connected next actions. |
| Engineering | Systems workspace (Canvas/Table/Reader), systems/interfaces, calculation chains, power/energy and single-axis pointing. |
| Simulations & studies | Vertical flight, prescribed planar ascent, serial staging, orbital simulation, scenarios and envelope studies. |
| Evidence & review | Coverage, changes, design comparison, sources, test data, simulation imports, engineering actions and report. |
| Project setup | Authoring, rocket example creation, import/templates, empty project creation and AI quality/tools. |

Each area opens a short destination list. Once a tool is selected, only that area's links appear below the five main choices. The system tree and Canvas/Table/Reader controls appear in the Systems workspace. **Project actions** groups new/import/report commands in the header. Existing contextual links continue opening the relevant tool.

## Return without losing your place

The breadcrumb starts with Projects, then the selected project, work area and tool/item context. Parent breadcrumbs are clickable. The in-app Back arrow and browser Back/Forward use recorded internal locations. Saved project/revision, tool, system, view mode, selected engineering item and context panel are addressable in URL fragments; opening the same link in the same accessible workspace restores that location. Project IDs are navigation identifiers, not shared access or permission to read a different user's workspace.

Navigation URLs contain no input values, unsaved draft content, credentials or AI questions. A URL is not a backup of a draft or of exploratory form inputs. Hosted invitation sessions and workspace isolation remain enforced by the server.

Changing tools within the same saved project/revision keeps the shared project draft. Switching to another project or revision asks before discarding changed draft data. Declining Back restores the current location. Reload/exit uses the browser's unsaved-edit warning. An open authoring record editor requires confirmation before browser traversal; an open thrust-profile edit must be applied or cancelled before navigating. Route restoration locks project edits while a different saved context is loading.

Unsaved standalone exploratory forms (for example, unsubmitted scenario/import configuration) are not a persistent scratchpad. Their explicit save actions remain necessary. Browser Back from the first recorded 6D location can leave the application, as it does on ordinary websites; the in-app Back arrow is disabled there.

## Typography

The interface uses native Apple/system sans and mono stacks, with an optional locally supplied Geist variable taking precedence. No font is downloaded. Headings use tighter tracking; labels use uppercase tracking; identity and quantitative readouts use mono/tabular numerals while large findings retain their size. Ink/off-white surfaces and subtle borders follow the supplied palette. Essential secondary text uses the darker `#67676b` for readability rather than applying the lighter decorative gray to every instruction. Requested smoothing declarations are included, but actual rendering depends on the browser and operating system.

## Scope

Opening a view does not request an AI investigation, Tavily search or LangSmith upload. Calculations retain explicit run actions. Super remains the selected Assistant; three-model selection and owner accounting-display changes are separate approved proposals awaiting their own start instruction. This navigation work is not final interface polish or a claim that an outsider has completed a usability study.

[Acceptance](WORKSPACE_NAVIGATION_ACCEPTANCE.md) · [Recorded delivery](WORKSPACE_NAVIGATION_RESULTS.md)
