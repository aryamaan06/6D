# Six-issue usability delivery evidence

October 26, 2026. The actual owner application was restarted and verified at **http://127.0.0.1:8768/**, build **0e93a5ca07d3**, with `restart_required: false`. [User guide](SIX_ISSUE_USABILITY.md) · [Acceptance](SIX_ISSUE_USABILITY_ACCEPTANCE.md) · [Sanitized checks](validation/SIX_ISSUE_USABILITY_CHECKS.json)

## What changed and why

The Overview run handler previously skipped a deliberate run when a saved result existed. It now accepts that explicit action and shows progress/completion; duplicate in-flight starts remain blocked. Guided review previously conflicted with landing-page display rules and could navigate away; it now toggles visibly in place with a retained local preference.

The flat rocket was replaced by a locally rendered WebGL model with metallic shading and animated exhaust. Pointer capture, a drag threshold, animation-frame positioning, click suppression, viewport clamping and normalized local placement make dragging independent of asking. Keyboard movement, reduced motion and graphics-loss fallback retain access.

A shared target picker presents a short, grouped, duplicate-free list and keeps all specialist identities in Advanced. Source library now uses progressive, spaced forms and explains unavailable actions. Nemotron puts scope, model, question and Ask first, with technical context and earlier records expandable. One global sans stack covers human-readable text, while a more specific mono rule retains actual data/code styling. The source server allowlist and build fingerprint include both new local modules.

## Verification

| Evidence | Result and limits |
| --- | --- |
| Affected Python regressions | **81 methods: 80 passed, one Windows Docker-unavailable skip.** Workspace assets/API, connected review, sources/research, owner boundaries and hosted packaging. Not a full-suite claim. |
| Browser journeys | **49 groups passed:** 13 six-issue acceptance, eight model-choice, eleven clarity/owner/visitor, seventeen navigation. Isolated synthetic providers; no external requests or unexpected responses/browser errors. Counts overlap earlier milestone checks. |
| History contracts | **Six Node contracts passed.** |
| Runtime source policy | **64 Python files passed** the LF consistency check; exact Git-byte matching is checked after commit. |
| Actual owner preservation | **27 original table/file checks matched** after restart: projects, saved revisions/runs, investigation/research histories, reservations/approval, settings and encrypted credential files. Private raw hashes remain local. |
| Connections | Nebius, Tavily and LangSmith restored as present and remembered, with no credential error. Default Super, owner approvals/accounting and hosted limits remain unchanged. |

The new browser journey deliberately calculates an already-calculated saved revision twice, holds one run to verify the progress/double-start guard, checks new run identities and unchanged numerical results, opens the guide from the landing pages, and checks actual WebGL frames. It also covers drag persistence and keyboard/resize/mobile behavior, reduced motion, context loss, all three model choices, explicit synthetic Nemotron/Tavily starts, exact Advanced targets, an unsaved preview handoff, separate source-save/link actions, computed fonts and protected visitor controls. Canonical fixture inputs and allowance are preserved. The older navigation pack covers Back/Forward, reload, stale request handling and unsaved-draft/profile guards.

Desktop and narrow-screen screenshots were inspected locally for the conversation, source library and rocket; private captures are not published. An intermediate shader refinement exposed a cross-stage uniform-precision link failure. Matching explicit uniform precision corrected it, and the final actual-WebGL acceptance check passed. A static fallback is not reported as a successful 3D draw.

No real inference, search, telemetry upload, credential entry or paid request was made for this interface milestone. Existing provider qualifications remain historical under their captured sources. These are interface/API regression checks, not new live-model semantic qualification, independent engineering validation, physical simulation validation or public-hosting evidence. Visual polish remains subject to founder feedback.

## Reproduce

Use `PYTHONPATH=src;tests` on Windows (`src:tests` on POSIX):

```console
python -m unittest test_workspace_navigation_assets test_workspace_api test_connected_review test_workspace_sources test_workspace_sources_api test_workspace_research test_source_research_api test_owner_settings_boundary test_hosted_packaging -q
node tools/check_usability_browser.mjs
node tools/check_model_choices_browser.mjs
node tools/check_clarity_browser.mjs
node tools/check_navigation_browser.mjs
node --test tests/workspace_navigation.test.cjs
python tools/check_source_consistency.py --git-ref HEAD
```

Browser harnesses need Playwright and Chrome; set `PLAYWRIGHT_MODULE` and `SIXD_TEST_PYTHON` if using another installed runtime. They create isolated temporary workspaces with synthetic transports, never the owner's saved projects or keys. Their default run outputs remain ignored under `work/`.
