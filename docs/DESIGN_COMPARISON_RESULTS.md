# Recorded design comparison — October 21, 2026

Delivered locally at http://127.0.0.1:8768/, build `762123dc019a`. Refresh the application and open **Compare designs** in the left sidebar. October 30 remains the submission deadline.

## Delivered behavior

Choose two exact saved runs or hypothetical scenario cases, then explicitly compare them. The view shows each record's identities, changed supplied inputs, original findings, result, criterion, signed margin or exact-target difference, and supporting assumptions, exclusions and source versions. Revisions awaiting checks are listed without invented results. Draft values are excluded.

For unchanged comparable criteria, larger signed margins improve `<=`/`>=` results; smaller absolute differences improve exact `==` results. Equality has no inferred tolerance. Changed limits receive a separate criterion-change label. Changed model definitions, operators, units, verification versions, assumptions or upstream scalar-chain context suppress like-for-like trends. Unassessed diagnostic outputs remain labelled, with no assessed margin. Added or removed requirements describe scope changes.

Scenario cases remain hypothetical. Case comparisons require the same baseline run; a run/case comparison requires that exact baseline. Different baselines and historical implementations remain inspectable with explicit limitations and withheld trends. No aggregate winner or mission assessment is produced.

Catalogue and comparison reads each use one SQLite snapshot. Exact selectors never follow a later rerun. Selecting or refreshing choices invalidates the old display and exports; delayed responses cannot overwrite a new selection or project. JSON download retains the exact captured server response, including original integer text. Visible quantities and expanded model/source context use server-produced text to avoid browser number rounding. Print expands captured evidence and restores disclosure states afterward.

This view performs no calculation, revision save, source retrieval, model selection or paid inference. It requires no API key.

## Verification

- All 164 affected regressions passed across comparison, workspace/API, scenarios, source library, actions, test-evidence/report routes and local launcher modules. After the final exact-context display change, all 30 comparison backend/HTTP groups passed again. These counts overlap; they are not a full-repository suite claim.
- Six real-API Chrome workflow groups passed on the final code: explicit selections and hand-checked tradeoffs; byte-identical JSON and expanded PDF output; selection invalidation, relaxed criteria and unit gaps; hypothetical/baseline compatibility; 390px layout; project switching and navigation without execution. No page errors or external requests. The disposable fixture database matched its post-seeding baseline exactly.
- Six additional isolated async/UI groups passed for blank selection, draft exclusion, delayed comparison/catalogue disposal, wrong-project response rejection, refresh invalidation and raw export. Nine separate frontend harness checks additionally covered diagnostic/truncation labels, safe references, print-state restoration and layout; these overlap the integrated groups.
- Six separate-agent constructed consistency groups checked the supplied 100 N to 64 N example: `<=150 N` margins 50 to 86 N improve; `>=50 N` margins 50 to 14 N worsen; `==100 N` absolute differences 0 to 36 N worsen. They also covered exact integer display, criterion relaxation, scenario baselines, scalar-chain context and no recalculation/writes. This is automated consistency review, not independent human engineering validation.
- Eight final checks passed on the delivered main application, using two of its 12 existing saved runs, exact captured export and navigation back through actions, sources and reports. The selected older implementation was correctly labelled historical and received no improvement claim.
- All existing database rows, provider configurations and selected historical artifact hashes match the pre-milestone baseline. No schema or founder demonstration record was added. No paid calls or changes to the USD 29.50 cumulative ceiling, USD 2.30350988 conservative reservations or active model selection. Reservations are not billed charges.

Private ignored evidence includes `work/design-comparison-regression.json`, `work/design-comparison-browser-results.json`, `work/design-comparison-ui-results.json`, `work/design-comparison-ui-visual-results.json`, `work/design-comparison-independent-review.json`, `work/design-comparison-current-app.json` and `work/design-comparison-baseline.json`.

## Boundaries

The catalogue shows the latest 100 runs and 20 scenario studies, each already bounded to 16 cases. Omitted catalogue history is disclosed. A captured comparison is limited to 64 MiB. Explicit older identities remain resolvable within the selected project/revision boundary.

Trends describe declared criteria under supplied conditions. They do not prove physical equivalence, causal hardware improvement, source accuracy, complete vehicle validity or mission success. There is no unit conversion, interpolation, optimization, probability, simultaneous multiphysics solver or automatic ranking. Digests provide unsigned consistency checks.

This is a local delivery. No GitHub push or hosted deployment is implied. Tavily and LangSmith remain deferred.
