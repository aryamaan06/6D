# Rocket companion and central evidence — delivery

October 26, 2026. Open **http://127.0.0.1:8768/** and refresh for build **e92a749b1f48**. The actual owner server was restarted normally; health reports no restart requirement. [Guide](ROCKET_ASSISTANT.md) · [Acceptance](ROCKET_ASSISTANT_ACCEPTANCE.md) · [Sanitized checks](validation/ROCKET_ASSISTANT_CHECKS.json).

## The two requested changes

**One ordinary AI entry point.** A small animated rocket with flame and gas exhaust stays near the lower left across work areas. Its local SVG/CSS animation needs no image download, respects reduced-motion preferences and supports keyboard access. Clicking it opens a centered native dialog with **Ask Nemotron** and **Find references** tabs. Opening, selecting a model or closing sends no inference/search request.

The separate Assistant tab, toolbar project-investigation action and ordinary standalone research section are removed. Specialist investigation buttons are also hidden consistently when asynchronously rendered; the rocket is the normal question/search entry point. Owner settings still manages private connections, qualification and LangSmith metrics; it is not another ordinary chatbot.

The companion uses the existing requirement/project investigations, Nano/Super/Ultra selector, captured evidence/history, active-job guards and approved accounting. It does not alter generation settings, model defaults or acceptance rules. Unsent questions and search drafts are retained by scope in browser memory during navigation/close/reopen, not promised across refresh. Earlier answers and scope/data descriptions are expandable. No saved project on Projects means a clear local instruction to choose one, not a fabricated AI answer.

Tavily keeps explicit search, saved-result preview and manual source review. **Use in source form** waits for the actual source editor to be ready, copies into an unsaved form, and only then closes the rocket. Saving and linking remain separate user actions. Failed handoffs retain the preview; stale completions cannot overwrite a newer context. A reference request stays tied to its captured project while pending and cannot silently become a search in a different selected project.

**No separate right-hand section.** Inspector and Evidence now share a full-width central card near the top of the Systems workspace. A requirement's primary finding and criterion sit together; declared source/limit fields and assumptions/supporting records are folded by default. Draft fields stay editable in their normal workflow. Exact quantities, charts, source identities, assumptions, exports and saved history remain accessible. Selection brings the central card into view instead of requiring a narrow independently scrolling rail. Browser Back/Forward may close the conversation; reopening reads retained outcomes without repeating provider work.

## Verification

- **48 affected offline Python methods: 47 passed, one Windows Docker-unavailable skip.** Covered workspace/static assets, AI API, reference search, hosted owner boundaries and packaging. An initial selection found one stale final-stylesheet expectation; the assertion now verifies that native typography precedes the local rocket/layout stylesheet, and both new assets are served without side effects. The final combined selection passed. This is not a full-suite run.
- **48 browser groups passed:** 12 rocket acceptance, eight model-choice, eleven clarity/owner/visitor and seventeen navigation groups. The rocket check includes animated/reduced-motion behavior, centered desktop/mobile layout, context changes during delayed Tavily loading, no extra AI entry points, both AI scopes and manual source handoff. Browser providers were synthetic, with zero external requests or real provider calls. Asynchronous source-editor assertions wait for actual prefill rather than an intermediate empty form.
- **Six Node navigation contracts passed.** Runtime source consistency checked all 64 Python files with LF policy. Numerical solver sources did not change.
- **27 original-state checks matched:** existing owner database tables, reservations/approval, configuration and encrypted credentials were unchanged. No owner project, revision, calculation, source, investigation or comparison was added by this interface milestone.
- Nebius, Tavily and LangSmith restored as connected and remembered without credential errors. The retained Ultra six-case result still matches its investigation-source vector; no new paid evaluation was run or implied.

Reproduction (set `PYTHONPATH` to `src;tests` on Windows or `src:tests` on POSIX):

```console
python -m unittest test_workspace_navigation_assets test_workspace_api test_owner_settings_boundary test_hosted_packaging test_workspace_research test_workspace_ai_api -q
node --test tests/workspace_navigation.test.cjs
node tools/check_rocket_browser.mjs
node tools/check_model_choices_browser.mjs
node tools/check_clarity_browser.mjs
node tools/check_navigation_browser.mjs
python tools/check_source_consistency.py --git-ref HEAD
```

Browser checks need local Playwright/Chrome. Raw snapshots, synthetic browser logs and screenshots remain ignored under `work/`; only sanitized outcomes are published. This is an interface/access refinement, not additional physics, general semantic qualification or public hosting.
