# Part 2 — readability and organization

Delivered October 26, 2026. Refresh **http://127.0.0.1:8768/** for build **4e50d1e86a6c**. [Acceptance](PART2_READABILITY_ACCEPTANCE.md) · [Verification](PART2_READABILITY_RESULTS.md)

## Read a page without repeated introductions

The workspace supplies one primary page heading and concise introduction. Repeated decorative titles/lead paragraphs inside tools are suppressed; actions, revision identity and separate model limitations remain. Overview retains its own project heading. Long supplied project descriptions are under **Project purpose, assumptions and scope**, and calculation-scope warnings remain visible.

## Open the records you need

**Project setup → Author project** groups **Inputs and limits**, **Model definitions** and **Requirements** into counted disclosures. Inputs separate model parameters from requirement limits. Individual records reveal their exact ID, source, bindings and existing edit/remove controls.

Open a group and a record, then choose **Edit draft** to change it. Applying an edit keeps the relevant disclosures open through the normal redraw/preflight process. These open/closed choices are transient presentation state; they do not save a project or write browser storage. The shared draft, validation, dependency guards and explicit Save revision workflow remain unchanged.

## Compact display, exact evidence

Ordinary numeric summaries share seven significant digits, with grouped thousands. Values below `0.0001` in magnitude or at/above `10,000,000` use scientific notation with six significant digits. For example, `6126.145572278846` displays as `6,126.146`. Small nonzero values are not displayed as zero, and nonnumeric/nonfinite values are not coerced into valid numbers.

- In Overview, select a requirement to open **Exact recorded values**.
- Reports retain exact table/plot records and original evidence exports.
- Flight views expose expandable exact saved metrics/diagnostics and selected samples; other viewers retain original samples, provenance and JSON exports.
- Hover tooltips supplement the explicit exact-value route. A touch user does not need a hover to inspect the saved evidence.

Rounding never determines a finding. Two rounded numbers can look equal while the original values differ; their recorded status is preserved. Exact decimal strings supplied by comparison records remain exact rather than being coerced through browser numeric conversion.

Human-readable SI labels use superscripts, including native dropdown labels. Canonical option values, editable unit strings such as `m^3/s^2`, raw CSV, source quotations, JSON and receipts keep their original notation and precision. Numeric summaries and record identities use the coordinated mono font; ordinary copy retains the shared UI font.

## Tell similar projects apart

Project cards and the project picker add a short actual-ID suffix when names collide, including case/whitespace variants. The suffix extends if necessary to distinguish IDs; it is deterministic for the same records and does not depend on list order. Full IDs remain in accessible labels/tooltips and project setup. Supplied creation dates provide additional context.

This changes display labels only. Original names, IDs, revisions, routing values and ordering are preserved. No qualification/example project is silently deleted, renamed or hidden. Type/model hints appear only if actually supplied by the project-list data; the current list API does not supply those hints.

Printing a report expands its evidence/project-scope disclosures and restores their prior on-screen state afterward. Project/evidence JSON exports retain original data. Numerical models, three-model AI choice, remembered service connections, approvals and accounting are preserved. Part 3 companion placement/context/handoff refinements remain separate and unstarted.
