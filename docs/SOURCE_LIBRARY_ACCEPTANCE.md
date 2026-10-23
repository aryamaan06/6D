# Project source library acceptance

## User task

An engineer records a supplied reference, links it to the precise requirement, model assumption or recorded finding it supports, and reviews the link after a relevant change. References travel with the report as supplemental context; the original calculation and its finding remain unchanged.

## Acceptance cases

1. Add a reference with title, HTTP(S) URL, excerpt and source details. Saving it performs no URL retrieval, calculator execution or AI request. The reference remains available after reopening the project.
2. Link a reference to a declared requirement, a particular maintained model assumption and a saved finding. The visible link identifies its exact target, project revision and pinned source version.
3. Change a requirement limit or relevant bound input in a new project revision. Affected links show that they need review. A change to an unrelated, unbound input does not by itself invalidate a requirement's reference context.
4. Edit a source. The earlier version remains readable and existing links retain its original excerpt and details. A link requiring attention cannot silently adopt the new source version.
5. Confirm a link review explicitly against the current saved context. Preserve the earlier link version and show the current source/target context. This acknowledgement changes no engineering requirement status and is not physical validation or authenticated approval.
6. Replace or rerun a finding. Links to the prior recorded finding retain that original context and do not automatically claim to support the new finding. Removed targets remain visible with an unavailable-target or review warning.
7. Inspect a requirement and the report. Linked references appear separately from numerical evidence and include supplied excerpts, safe source links, version identifiers and review reasons.
8. Export a combined review. It includes a frozen source-library snapshot and its digest separately from the unchanged canonical engineering receipt. Its enclosing export digest covers the added snapshot. Printing retains linked reference context.
9. Show draft context honestly: unsaved edits cannot be used to create, edit or confirm persisted source links. Reopening an older revision must not show sources or link versions first added in a later project revision as contemporaneous records.
10. Reject unsafe URL schemes, URL credentials, malformed targets and stale source/link version writes. HTML-looking source text renders as text. Existing data cannot be overwritten through a stale browser form or another project's source ID.
11. Preserve all existing project, revision, run, investigation, provider-configuration and spending-ledger records. Local backups include the new tables through the existing workspace SQLite backup. No source-library interaction incurs paid inference.

## Interpretation limits

“Linked” describes a recorded source/target association whose tracked context still matches. It does not mean the excerpt is accurate, that the reference supports the stated claim, or that a model is physically valid. Rechecking source relevance requires a person. Digests are unsigned consistency checks. References never override calculated results or close unsupported engineering coverage automatically.

This document defines acceptance. Actual observed results belong in a separate milestone results record.
