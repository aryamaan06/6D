# Engineering action queue acceptance

## User task

An engineer turns an unmet/unassessed saved finding or a source-review flag into a concrete action, records the missing evidence and next check, tracks the work, and records its closure with linked support. Relevant later changes flag the action without rewriting the earlier workflow or numerical evidence.

## Acceptance cases

1. Enumerate origins from actual saved unmet/unassessed findings and source links needing review. Do not claim an unrun project has a calculated failure. Reading the queue creates no actions, runs no calculator, fetches no URL and makes no provider request.
2. Explicitly create an action with a supplied title, next check, missing evidence and completion criteria. Guidance remains editable and clearly does not claim completed work.
3. Preserve every saved action version and workflow note. Normal forward transitions are To do → In progress → Ready for review → Closed; an action cannot jump directly from To do to Closed. Reopening work is explicit.
4. Refuse closure without a nonempty closure note, at least one selected current support record, the required prior workflow state, and matching origin/support context. A source or result alone does not prove relevance or completion of the action's declared criteria.
5. Closing an action leaves the canonical requirement status, calculation receipt, project revision and provider ledger unchanged. A nonpassing finding can remain nonpassing after a documented investigation is closed.
6. Pin selected supporting findings and source versions. A later source edit or rerun flags the action. Saving an unchanged list of support IDs must not silently replace captured support with newer versions.
7. Change a relevant bound input, requirement criterion or explicit upstream calculation dependency. Flag the affected action. An unrelated input edit must not by itself change another action's tracked model dependencies. Distinguish that dependency check from a finding-origin action becoming unavailable before a new run, or requiring provenance review after its run is replaced.
8. Start an action from a source link that is already flagged. Make a second relevant design change while the source link still has the same visible status/reason text. The action must detect the changed target context rather than comparing only the repeated reason text.
9. Keep a closed action's recorded workflow state while separately flagging changed context. Explicit context review retains earlier history, clears support/closure fields, and reopens Closed or Ready for review work to In progress. It does not automatically close work when an origin later becomes met or a source flag clears.
10. Refuse stale queue digests and action base versions before writing. A source edit, finding rerun or simultaneous action update cannot cause an unseen context or support version to be adopted. Null or malformed context tokens must not bypass the public API's concurrency check.
11. Keep unavailable origins visible with their original context and a clear warning. Historical project revisions show only action versions recorded at or before that selected revision. Draft and historical controls are read-only.
12. Show scoped actions beside the relevant requirement and in reports. Printed reports retain workflow and review-state distinctions. Combined JSON captures action/source snapshots inside the same database read transaction; its digest covers the added material and its original numerical receipt remains unchanged.
13. Preserve escaping for action text, notes and source excerpts; user content cannot inject markup. Controls remain usable at a narrow mobile viewport, and stale asynchronous responses cannot overwrite the current project's queue.
14. Reopen the workspace and recover a local backup with action history intact. Keep all pre-existing project, revision, run, investigation, source-library, provider-configuration and spending-ledger records unchanged except for explicitly requested new action rows.

## Interpretation limits

Workflow state is not an engineering verdict. Completion criteria, support relevance and closure notes are user declarations. No authenticated team approval, independent human review, hardware validation or mission readiness follows from an action's closure. Digests detect inconsistent or stale records; they are not signatures or proof of truth.

This document defines acceptance. Actual implementation and verification results belong in a separate milestone results record.
