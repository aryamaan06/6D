# Engineering actions

Use **Engineering actions** to track the work arising from a saved finding or a source-link review flag. The queue runs locally without an AI connection, Tavily or LangSmith.

## Create and work on an action

1. Run the supported checks for the saved project, or inspect a source link that needs review.
2. Open Engineering actions and select the finding or source-review flag to address. Available origins are recorded unmet/unassessed findings and source links needing review; the queue does not invent a calculated failure when no review exists.
3. Enter an action title, the next engineering check, missing evidence and completion criteria. Suggested steps are starting guidance to inspect and adapt, not evidence that the work has been done.
4. Save the action. Move it through **To do → In progress → Ready for review → Closed** as the work proceeds. Notes and earlier versions remain in its history.
5. Before closing, select supporting saved findings or source records and record a closure note. The action must be ready for review, and its tracked context and support must still match.

Supporting records capture their exact saved versions. Their relevance and whether the supplied completion criteria have been satisfied remain a user judgement. In particular, a manually entered reference is not automatically verified evidence.

## Changes and review

A changed design dependency, replaced finding, edited supporting source or missing origin can flag the action for review. The queue keeps the earlier context and support visible. It does not silently move an old support link onto a new result or source version.

A finding-origin action tracks a particular recorded run. Saving a revision before running its checks can make that origin temporarily unavailable, and a new run can require provenance review even if the calculated value is unchanged. This does not by itself mean the physics changed.

A previously closed action can remain **Closed** while also showing **Needs review**. These describe different things: the recorded workflow decision and whether its captured context still matches. Inspect the change and explicitly adopt the new context before continuing. Reviewing a closed or ready-for-review action reopens it in progress and clears its current support selection and closure note; the previous versions remain in history.

Every saved action change checks the exact displayed queue context and its previous version. If another window changes the underlying data, refresh and review it before saving. Drafts and older project revisions are read-only.

## Findings, reports and backups

Closing an action records a workflow decision. It never makes an engineering requirement pass, clears unsupported coverage, verifies physical testing or authorizes a mission. A closed investigation may document why an unmet requirement still exists.

The report presents actions separately from calculated evidence. Combined review JSON captures the action queue and source library as supplemental snapshots, with their own identities and an enclosing export digest. Original numerical receipts are unchanged.

The normal local backup includes action versions in `workspace.sqlite3`. This milestone does not assign authenticated reviewers, send notifications, run checks automatically or verify that completion criteria were actually fulfilled.
