# Engineering action queue — October 21, 2026

Delivered locally at http://127.0.0.1:8768/, build `6f7c9a5db4b2`. Open **Engineering actions** in the left sidebar, or **Track engineering action** in an unmet/unassessed requirement's inspector. October 30 remains the submission deadline.

## Delivered behavior

Actions are explicitly created from a saved unmet/unassessed finding or a source-link review flag. Deterministic suggested steps use the existing recorded-evidence guidance and remain editable. Each action records a next check, missing evidence, declared completion criteria and notes.

The board tracks To do, In progress, Ready for review and Closed. State changes append immutable versions. Closing requires the prior review state, matching recorded context, a completion note and at least one selected supporting finding or manual source. Neither the relevance of that support nor fulfilment of user-declared completion criteria is automatically established. A closed action can document why an engineering finding remains unmet or unassessed.

Supporting records retain their exact captured source/finding versions. Relevant source, dependency or finding changes flag the action without changing its saved workflow state. Explicit context review records a new origin context, clears current closure/support selections and reopens closed or ready work to In progress. Earlier closure and support remain in history. The captured origin revision is stored separately from the latest action-version save revision.

All action writes require the displayed queue digest, latest saved project revision and appropriate action version. Drafts and historical revisions are read-only. Refreshing a form does not silently adopt an unseen context. No automatic actions, calculations, notifications, network retrieval or paid calls occur.

Action summaries appear in requirement/model inspection, Reader, changes and full reports. Combined JSON captures actions and sources within the engineering review's existing SQLite read transaction before recomputing the export digest. Printed reports show action details and expanded captured support. Original numerical receipts remain unchanged. The existing local SQLite backup includes action versions automatically.

## Verification

- All 155 affected regression tests passed, including 18 backend action groups and six action HTTP tests. This is an affected run, not a full-repository suite claim.
- Five real-API Chrome workflow groups passed: inspector-scoped creation; four states with closure gates and unchanged unmet finding; report/print/combined JSON; changed-design review and explicit reopening with preserved history; 390px layout. Zero page errors or external requests.
- Eight isolated UI groups passed, including safe text rendering, pinned evidence, stale form tokens and read-only historical/draft behavior. These overlap integrated checks.
- Six separate-agent consistency groups exercised a constructed scalar chain and source-review actions. They checked repeated upstream changes despite unchanged review-reason text, unrelated dependency stability, preserved support pins, explicit reopening, stale-context rejection and historical numerical preservation. This is automated consistency review, not independent human engineering validation.
- Eight final read-only checks passed on the delivered main application. No writes or external requests were attempted.
- All pre-existing database rows, source-library records, provider configurations and selected historical artifact hashes match the milestone baseline, including 12 saved runs. The only main database schema addition is an empty action-version table. No demonstration action was inserted into the founder workspace.
- No paid calls or changes to the approved USD 29.50 cumulative ceiling, USD 2.30350988 conservative reservations or active model selection. Reservations are not billed usage.
- Browser navigation exposed normal cancelled-read connections being misreported as storage failures. GET/POST handlers now close those ended connections without inventing a storage error or retrying a committed write. The final browser and affected regression runs include this correction.

Private ignored receipts: `work/action-queue-regression.json`, `work/action-queue-browser-results.json`, `work/action-queue-ui-results.json`, `work/action-queue-independent-review.json`, `work/action-queue-current-app.json` and `work/action-queue-baseline.json`.

## Boundaries

The queue supports 100 actions, 30 saved versions per action and 20 supporting records per action. It records manual work state; it does not authenticate reviewers, verify actual task execution, infer source relevance or issue engineering approval. Finding-origin actions track a specific saved run; replacing that run can require provenance review even when a calculation was reused. A new revision awaiting checks may temporarily make a finding origin unavailable.

Task assignment, notifications, automatic checks, action deletion/retirement and AI-managed work execution are not implemented. Tavily and LangSmith remain deferred. Source support remains user-supplied, and an empty or fully closed queue is not a mission-completeness or readiness assessment.
