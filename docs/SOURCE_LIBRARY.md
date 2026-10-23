# Project source library

Use the source library to keep supplied references beside the engineering records they explain. It works locally without Tavily, LangSmith or an AI connection.

## Record and link a reference

1. Open a saved project revision and its source library. Save or discard any draft before changing library records.
2. Add a title, HTTP(S) URL, relevant excerpt and source details. Include useful provenance such as author, publication date, edition, section/page and why the reference applies.
3. Choose the source and the specific target: a requirement, a maintained model assumption, or a recorded finding. Add a note explaining the connection.
4. Save the link. Its source version and target context are recorded explicitly. Open the linked requirement or report to inspect the reference alongside the calculated evidence.

URLs are not fetched or checked. An excerpt is user-supplied text, not an authenticated quotation or proof that its claim is true. Source records belong to the selected project; they are not shared across projects automatically.

## Changes and review

Editing a reference creates a new source version. Existing links retain their pinned excerpt and source details. Relevant project changes or source-version changes can flag a link as needing review. A new run does not silently transfer a reference from an earlier finding to the new finding.

Inspect the original source, target and review reasons before confirming a link review. Confirmation records your explicit acknowledgement of the current saved context and retains the earlier link version. It does not validate the source, make a requirement pass, authenticate an engineering approval or certify a vehicle.

Link creation and confirmation check the exact displayed library context. If another window changes a reference or reruns the selected finding before you save, 6D refuses the stale action. Refresh and inspect the updated records before trying again.

“Linked” means the tracked records match the recorded association. The person reviewing the project must still decide whether the source is relevant, complete and trustworthy.

## Reports, history and backups

Linked references are supplemental material in the report, separate from model-produced numerical evidence. Combined review exports capture their own source-library snapshot and digest. Existing calculation receipts are not rewritten when references are added or edited. An annotation added later must not be mistaken for evidence captured by the original calculation.

Use **Export combined review JSON** to include reference records, or **Print report / Save PDF** for the visible report. **Export evidence JSON** preserves the original numerical receipt rather than adding later annotations.

The normal local workspace backup includes the source-library tables in `workspace.sqlite3`. The backup remains private project data; source excerpts and notes may themselves be sensitive. This feature does not publish sources or connect a third-party service.

This milestone adds manual reference recording and context tracking. Automatic retrieval, citation verification, document ingestion and source-grounded AI interpretation require separate capabilities and validation.
