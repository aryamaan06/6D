# Part 2 — readability delivery evidence

October 26, 2026. The actual owner application is verified at **http://127.0.0.1:8768/**, build **4e50d1e86a6c**, with `restart_required: false`. [Usage](PART2_READABILITY.md) · [Acceptance](PART2_READABILITY_ACCEPTANCE.md) · [Sanitized checks](validation/PART2_READABILITY_CHECKS.json)

## Delivered scope

The shell owns the primary title/lead, with scoped CSS suppressing only known duplicate module introductions. Overview retains its project heading. Technical project descriptions and authoring input/model/requirement records use counted native disclosures, with transient same-context expansion state and retained authoring handlers. Essential applicability warnings remain visible; print hooks expand/restore report details.

A shared display formatter supplies compact finite-number precision and safe SI notation. Primary quantities across overview, reports, flight/orbit, studies, imports, power/pointing and related comparison views use that policy where appropriate. Exact comparison strings, unsafe-integer guards, editable inputs, quotations and source/export JSON remain distinct. Explicit exact metrics/diagnostics/sample disclosures supplement tooltips. Component labels and Part 1 numerical-versus-fit distinctions remain intact.

Project display labels use stable unique actual-ID suffixes, extending on collisions without changing persisted names or IDs. Cards retain all records/actions and show only available metadata. No backend schema, numerical adapter, provider contract or spending limit changed.

## Verification

| Check | Result and limits |
| --- | --- |
| Affected Python regressions | **81 methods: 80 passed, one Windows Docker-unavailable skip.** Static/API, connected-review, source/research and hosted-owner boundaries; not a full-suite claim. |
| Focused Node contracts | **35 passed:** five number/unit, six project-choice, five coverage/exact-display, seven source-target, seven history and five tool-status cases. Includes tiny/extreme values, escaping, near-threshold rounding, ID collisions and unchanged captured data. |
| Navigation/readability browser | **26 groups passed.** Includes distinct project cards, compact/expandable exact values, original-value project export, grouped draft edit/preflight state, native unit labels, single primary headings, visible flight exclusions, print restoration, mobile layout and earlier navigation/profile guards. |
| Existing companion/source browser | **13 groups passed** with isolated synthetic providers: three-model choice, explicit calculations/asks/search, manual unsaved-source handoff/save/link, drag, WebGL/fallback and hosted boundaries. |
| Runtime source policy | **64 Python files passed** LF consistency; exact committed bytes are checked after commit. JavaScript syntax checks passed. |
| Actual app inspection | All 13 owner projects remain visible with distinct labels where needed. The saved walkthrough exposes 34 input records as 24 model inputs and ten requirement limits, plus six model definitions and ten requirements. No actual owner draft was edited. |

The browser total is **39 groups**. Both packs had zero external requests, unexpected HTTP responses and browser errors. The navigation fixture's POSTs were read-only setup/impact previews; companion operations used synthetic transports. Original fixture inputs, results, project lists and saved records remained unchanged. These counts overlap earlier work and are not independent physical or semantic validation.

Two early navigation-harness attempts used generic selectors for controls that belong to the setup hub/flight module. They were corrected to follow the actual UI entry points; final runs passed. The final numeric-font adjustment also passed the navigation/mobile regression. Original test failures are not treated as successful runs.

## Owner-state preservation and concurrent activity

**25 of 27 baseline table/file checks matched exactly.** During the build, one additional completed Nano investigation appeared in the owner's walkthrough, with its associated four request reservations. The build's UI tests did not use owner keys or initiate that investigation.

All **26 earlier investigation rows** still match their original combined checksum. The new reservation increase matches the added record, and the original budget approval identity/cap were verified unchanged against the pre-build digest after accounting for that increment. Other tables, settings and encrypted credential files matched. No activity, receipt or usage counter was reset or removed. The new record is retained as concurrent owner activity, not claimed as this milestone's live qualification.

Nebius, Tavily and LangSmith restored as present/remembered without credential errors. Default Super, cumulative approvals and hosted limits remain unchanged. No paid inference, search or telemetry upload was initiated by this build. Public deployment and Part 3 were not performed.

## Reproduce

Use `PYTHONPATH=src;tests` on Windows (`src:tests` on POSIX):

```console
python -m unittest test_workspace_navigation_assets test_workspace_api test_connected_review test_workspace_sources test_workspace_sources_api test_workspace_research test_source_research_api test_owner_settings_boundary test_hosted_packaging -q
node --test tests/display_units.test.cjs tests/workspace_project_choices.test.cjs tests/review_workspace_coverage.test.cjs tests/source_targets.test.mjs tests/workspace_navigation.test.cjs tests/workspace_tool_status.test.cjs
node tools/check_navigation_browser.mjs
node tools/check_usability_browser.mjs
python tools/check_source_consistency.py --git-ref HEAD
```

Browser tools require Playwright/Chrome and isolated temporary state. `PLAYWRIGHT_MODULE` and `SIXD_TEST_PYTHON` can select installed runtimes. Private raw records and screenshots remain ignored locally.
