# Part 1 — navigation and clarity results

Delivered October 26, 2026 at **http://127.0.0.1:8768/**, build **281ddb417a69**. The owner server was restarted normally and reports `restart_required: false`. [Usage](PART1_NAVIGATION_CLARITY.md) · [Acceptance](PART1_NAVIGATION_CLARITY_ACCEPTANCE.md) · [Sanitized checks](validation/PART1_NAVIGATION_CLARITY_CHECKS.json)

## Corrections

- New work-page/project/revision contexts synchronously reset to the top. Same-page renders retain position. The history controller temporarily selects manual scroll restoration and restores its prior policy on disposal. Cancelled navigation does not apply a new page context. The original lower-Overview report reproduction is now an automated regression, including accepted Back/Forward and immediate report opening after page entry.
- Simplified labels preserve component/stage/load-case context while replacing selected metric phrases. Battery and engine temperature choices remain distinct in both the pure helper tests and the actual rendered Assistant picker; exact identities and Advanced labels remain unchanged.
- Overview separates canonical calculated criterion counts from coverage/model-fit declarations. Existing saved coverage statuses supply the explanation and direct review action; no backend finding, model-fit judgment or requirement is changed.
- Project-scoped tool cards/navigation distinguish unconfigured, uncalculated, blocked, partly recorded and recorded states. Only matching current-revision completed results count as recorded. Historical/stale/prior results and unsupported GNC placeholders cannot silently establish unrelated tool availability. Badges use readable 13 px type and remain neutral about physical correctness.

An intermediate scroll implementation included a redundant later animation-frame reset. It was reduced to one synchronous reset before final verification, avoiding a delayed reset competing with subsequent interaction. Final navigation checks passed after that simplification.

## Evidence

| Check | Result |
| --- | --- |
| Affected Python modules | **81 methods: 80 passed, one Windows Docker-unavailable skip.** Workspace assets/API, connected review, sources/research, owner boundaries and hosted packaging. |
| Focused Node contracts | **23 passed:** seven route/history, seven source-target, four coverage-rendering and five tool-status cases. |
| Navigation browser | **21 groups passed** on isolated state: new scroll/coverage/tool/label cases plus saved-view reload, historical revision, draft consent, delayed loads, staged-profile guards, mobile layout and unchanged fixture receipts. |
| Existing companion/source browser | **13 groups passed** with synthetic transports: explicit calculations/investigations/searches, three models, drag/reload, WebGL/fallback, manual unsaved-source handoff/save/link, typography and hosted owner boundaries. |
| Owner preservation | **27 checks matched:** every baseline table plus settings/encrypted credential files. Projects, inputs, runs, histories, reservations and approvals were preserved. |
| Actual opening check | Current build verified; the real saved rocket's lower Overview link opened its report at `scrollY: 0`, with its heading at approximately 138 px in the viewport. |
| Connections | Nebius, Tavily and LangSmith restored as present and remembered, with no credential error. Default Super, approvals and hosted budgets remain unchanged. |
| Source policy | **64 runtime Python files passed** LF consistency; exact committed-byte matching is checked after commit. |

The browser totals are **34 groups**, not 34 additional engineering or live-model qualifications. Navigation permits only read-only draft-preview POSTs; the companion fixture permits its explicit synthetic operations. Both browser packs recorded zero external requests, unexpected HTTP responses and browser errors. Private raw snapshots/screenshots remain local. These scoped checks overlap earlier milestones and are not a new full-suite total.

No paid inference/search/upload, new numerical model, automatic rerun or public deployment was performed. This is interface/API verification, not independent physical validation, live semantic evaluation or founder acceptance of final polish. Part 2 and Part 3 remain unstarted.

## Reproduce

Set `PYTHONPATH=src;tests` on Windows (`src:tests` on POSIX):

```console
python -m unittest test_workspace_navigation_assets test_workspace_api test_connected_review test_workspace_sources test_workspace_sources_api test_workspace_research test_source_research_api test_owner_settings_boundary test_hosted_packaging -q
node --test tests/workspace_navigation.test.cjs tests/source_targets.test.mjs tests/review_workspace_coverage.test.cjs tests/workspace_tool_status.test.cjs
node tools/check_navigation_browser.mjs
node tools/check_usability_browser.mjs
python tools/check_source_consistency.py --git-ref HEAD
```

Browser harnesses require Playwright/Chrome and create isolated temporary workspaces. `PLAYWRIGHT_MODULE` and `SIXD_TEST_PYTHON` can select other installed runtimes. They never connect to the owner's actual project database or keys.
