# 6D workspace design preview

An isolated, clickable design artifact for review before replacing the existing application UI. The current web app, engineering backend and provider configuration are not changed by this preview.

Open the latest saved preview at http://127.0.0.1:8768/ . Bookmark it and refresh after updates. If it is not running, double-click Open-6D.cmd in Windows File Explorer at the repository root. No rebuild command is needed. See docs/OPEN_6D.md for the repeatable opening procedure. Local vendored Lucide icons and their license are in vendor/.

## Source and generated artifacts

- workspace-preview.source.html: editable interface, behavior and styles. This is an HTML fragment with one reference-data placeholder.
- fixtures/workspace-reference.json: deterministic snapshots captured by the existing Python engineering/lifecycle code. These are constructed examples, not measured hardware or a verified mission.
- workspace-preview.fragment.html: self-contained generated fragment for the in-conversation preview. Do not edit this generated file directly.
- ../tools/build_workspace_preview_data.py: regenerate the offline reference snapshots.
- ../tools/build_workspace_preview.mjs: bundle the source and recorded data without dependencies or network access.

From the repository root:

    python tools/build_workspace_preview_data.py
    node tools/build_workspace_preview.mjs

Use an available Python runtime for the first command. No API key or inference is needed. The fragment expects the conversation's supplied Lucide icon runtime; local browser inspection can inject the already-bundled local Lucide package. The ignored work/workspace-preview.html is the sandboxed browser inspection wrapper, not a hosted deployment.

## Implemented preview interactions

System selection, synchronized Canvas/Table/Reader modes, Inspector/Assistant tabs, requirement-scoped Investigate actions, local draft editing, dependency highlighting, revision staging, captured-reference replay, revision comparison, report reading and selectable JSON report export. The canvas supports pointer pan and zoom/fit; small layouts use readable item lists and an expandable system tree. Design notes explain the artifact and reset its walkthrough.

The assistant is a scripted explanation. Rerun affected checks replays an existing matching snapshot and makes no backend or model request. Replays cover 200/400/600/800 W and limits 300/320/350 K. Other positive edited values can be saved but cannot obtain invented results. Old evidence remains visibly stale until a matching replay. The control gap is a separate reference annotation backed by the fixture's control-gap variant, not an additional assessed requirement in the thermal snapshot.

The report export displays selectable JSON because the conversation's sandbox may prohibit file downloads. It does not require clipboard access or an external service.

## Not implemented by this milestone

Browser project APIs, shared persistence, live contextual project investigation, per-task model routing, real targeted backend reruns, general JSON/CAD/document import, team branching/approval, dynamic mission simulation and hardware/operational integrations. The preview's local revision state is not authenticated team review history.

The app's existing numerical behavior is unchanged. See docs/WORKSPACE_DESIGN_REVIEW.md for the founder walkthrough and recorded validation summary.
