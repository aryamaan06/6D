# Build 3 — delivery and measured results

Delivered October 26, 2026. Refresh **http://127.0.0.1:8768/**; health reports **eee28a7fcd10**, with no restart required. [Guide](BUILD3_CLARITY.md) · [Acceptance](BUILD3_CLARITY_ACCEPTANCE.md) · [Sanitized checks](validation/BUILD3_CLARITY_CHECKS.json).

## Delivered behavior

Overview connects Design, Calculate, Change inputs, Recalculate, Review changes and Report. A result legend distinguishes met, unmet, not assessed and not calculated. Prepared rocket thrust values are labelled as a teaching recipe; ordinary input editing remains available. Exact engineering quantities, thresholds and reports are preserved.

Ordinary Assistant views/history no longer display financial accounting. **Owner settings** separates Nebius, Tavily and LangSmith management, allowance and diagnostic controls. Amounts there describe the application's approved cap and conservative reservations, not the provider wallet or billed charges. Nano/Super/Ultra remain selectable; default Super is unchanged.

The protected visitor server blocks owner diagnostic GET routes and administrative POST routes, and public AI/hosted status exposes spending availability instead of owner allowance amounts. Actual limits still apply before inference. This is local operator versus invitation reviewer separation, not production team accounts or a claim that every technical field in an individual receipt is private. Public hosting remains pending.

Floating menus and static/dynamic native dialogs dismiss on an outside pointer action or Escape. Inside interactions and drags that start inside do not close them. Existing cancel/close cleanup clears unsaved key fields. Edited project authoring dialogs ask before discarding entries; declining retains them. Inline explanatory disclosures retain their normal behavior.

## Ultra: historical 2/6 and fresh 6/6

October 16 comparison `5f1c35cfd6b245168496c4dce1ce9828` attempted three Ultra cases. Two completed. The third was blocked by a wording-check false positive on correct negation about physical impossibility; the remaining three were **untested**, not failed. The negation check was corrected previously, but the old record never became a fresh six-case qualification. Build 3 preserves it and displays attempted, failed/blocked and not-run counts separately.

A separate source-current Ultra screen uses the maintained six-case evidence pack. Each independent case is attempted once. Ordinary rejected explanations remain failed while other independent cases may run; authentication, session, source, numerical recheck and spending failures stop further requests. No automatic retry, fallback or default promotion occurs. Status/prepare reads make no inference calls.

The authorized live screen completed **6/6 workflows**, with six attempted/completed, zero failed and zero untested:

| Constructed case | Captured finding | Workflow gate |
| --- | --- | --- |
| thermal-met | met | pass |
| thermal-exceeded | not met | pass |
| unsupported-control | not assessed | pass |
| invalid-unit | not assessed | pass |
| limit-only-change | not met | pass |
| held-out-drag | met | pass |

Receipt `291038383c1642ab952a98b246dd5dde` ran from `2026-10-25T17:04:22.772887+00:00` to `2026-10-25T17:05:07.414310+00:00`. It used **24 request reservations / USD0.748055 reserved**, below the USD2.10/36-request batch ceiling. The cumulative USD29.50 allowance/approval was unchanged; reservations became USD4.77454090. Reservations are not billed spend. No Tavily search or LangSmith upload occurred.

A separate coding-agent AI review detected no concrete contradiction in the six accepted explanations against captured evidence, statuses and changes. **This is not independent human validation, broad semantic accuracy, flight evidence or a general ranking of Ultra.** The four-case quality pack and whole-project source-bound qualifications remain separate. This screen does not silently promote their qualification flags.

## Verification and preservation

- Combined affected offline Python verification: **126 methods, 125 passed, one Windows Docker-unavailable skip**. This combines a 121-method regression selection and five separate owner-boundary methods; it is not full-suite discovery.
- **43 browser groups passed**: seven popup-dismissal, eleven clarity/owner/visitor, eight model-choice and seventeen navigation groups. Final review extended dirty-form confirmation to the close buttons and protected menu drags; the affected browser checks were repeated. One intermediate browser assertion raced the asynchronous dynamic-dialog cleanup; it now waits for that cleanup before asserting field disposal. Browser providers were synthetic; zero external inference/search/upload calls. Expected navigation cancellations were distinguished from HTTP failures.
- **Six Node history contracts passed**. JavaScript syntax checks and the LF check over 64 runtime Python files passed. Numerical solver sources did not change.
- **25 original-state checks matched**, covering existing database tables, configuration and encrypted credentials. Original 13 projects, 22 revisions, 36 runs, simulation and historical AI records were preserved. Only one separate Ultra-screen row was added; ledger growth exactly matches its reservations. Approval history and default model were preserved.
- Normal startup restored Nebius, Tavily and LangSmith as connected/remembered without errors. The saved six-case result still matches current investigation sources. No key was displayed or published.

Reproduce affected regressions with `PYTHONPATH=src;tests` on Windows (`src:tests` on POSIX):

```console
python -m unittest test_hosted_server test_hosted_runtime test_hosted_limits test_hosted_packaging test_ultra_workflow test_workspace_evaluation test_model_evaluation test_workspace_api test_workspace_ai_api test_workspace_research test_workspace_navigation_assets test_owner_settings_boundary -q
node --test tests/workspace_navigation.test.cjs
node tools/check_overlay_dismiss_browser.mjs
node tools/check_clarity_browser.mjs
node tools/check_model_choices_browser.mjs
node tools/check_navigation_browser.mjs
python tools/check_source_consistency.py --git-ref HEAD
```

Browser tools require local Playwright/Chrome. Private raw provider records, owner snapshots and browser logs remain ignored under `work/`; published summaries contain only scoped outcomes/nonsecret identifiers. Earlier failures and source identities remain intact.
