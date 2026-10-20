# Investigation reliability build

October 16, 2026, Asia/Calcutta. Stable application: http://127.0.0.1:8768/. Final build **43a76efc537e**.

## Delivered controls

- Required evidence reads are enforced before finish. A saved prior review makes its scoped revision comparison mandatory. A first review can inspect history optionally. Supported maintained calculations still require a fresh same-adapter reproducibility recheck; unsupported control has no invented solver.
- Safe failure codes distinguish per-case, batch and cumulative spending limits, request limits, transport problems, output truncation, invalid action responses, changed sessions/sources, recheck mismatches and rejected explanations. Fixed application messages and concrete next actions replace arbitrary exception text, including failures outside the model loop. No automatic retry or model fallback.
- The explanation gate blocks its fixed set of detectable contradictions and unsupported result assertions when the selected finding is unassessed with no valid captured metric. It catches the previously observed invalid-unit counterfactual. Rejected text/citations/reasons are preserved separately under rejected_interpretation; accepted summary remains empty, completion is not emitted, and the canonical engineering finding stays unchanged.
- Phrase checks recognize not_assessed and not_met, and handle additional explicit uncertainty/negation cases. They remain limited heuristics: acceptance does not establish semantic accuracy. Manual review remains necessary.
- The browser separates a stopped AI investigation from the engineering finding, displays useful next actions, and keeps rejected prose in a clearly labelled collapsed section. Saved guidance and evidence remain inspectable. It shows the configured development ceiling, reservations and remaining reservation capacity separately from provider billed usage/account balance.

## Comparison policy v2

The new case/report policy is versioned v2. It preserves earlier v1 receipts and scores. Nano, Super and Ultra receive identical evidence, questions, tool definitions, thinking profile and output ceiling. Current model-aware per-case reservation caps are USD 0.10, 0.20 and 0.35 respectively, with at most six requests each. The batch has its own USD 1.50 / 90-reservation ceiling, inside the existing cumulative ledger. These are headroom limits, not allocations that must be spent.

Before obtaining the private inference session, the service runs the exact constructed cases through an explicitly synthetic transport and memory-only forecast ledger. It exercises all available scoped reads, includes full configured output reservations and adds 15% headroom for request-size variation. This forecast must fit each candidate case and the batch; the configured cumulative ledger must have room for the complete batch ceiling. The build's offline forecast was approximately USD 0.9915 for 87 request reservations including headroom. A forecast does not guarantee actual completion or establish model quality.

Stronger models need all six current cases to pass, a review of the explanations, and a documented paired benefit. Reviewed baseline model/evidence failures can support a comparison; budget or transport failures alone cannot establish model superiority. There is no automatic model activation.

## Development allowance

Arya directed allocation of the stated USD 29.50 existing Nebius balance before submission and then authorized this build. The local allowance ceiling was explicitly migrated from USD 5 to USD 29.50. The same approval ID and prior USD 0.30432376 reservations were retained. The ID's historical usd5 wording remains unchanged to avoid introducing a second allowance. The ledger's allowance_changes table records the old/new ceiling, reservation total, authorization reference and time. The migration tool makes no provider request. A config/ledger mismatch fails closed; it cannot reset previous usage.

No additional card spending is authorized. These application controls do not alter provider billing preferences, certify an account balance or verify expiry. Earlier console images separated trial credits from account balance; the exact expiry of the reported balance remains unconfirmed. Useful accepted development tests should be prioritized before submission, with a separate ceiling for each explicit batch.

## Verification and live status

**The final 405-test regression suite passed; all eight focused model-selection tests also passed.** Coverage includes legacy provider behavior, allowance migration/audit, interrupted writes, shared reservations, private exception suppression, canonical evidence preservation, required reads, unsupported-prediction rejection, comparison integrity and the preserved orbital backend. Independent read-only review found a manager exception-text gap; the fix and regression test are included.

An isolated offline browser check passed six groups: supported completion; rejection of the exact unsupported counterfactual; unchanged canonical evidence; collapsed rejected text, citations and credential-free download; no requests on connection/navigation or automatic retry on reload; mobile layout without overflow and no JavaScript/CSP errors. Its synthetic fixture ledger is separate from Arya's ledger. Receipt: work/reliability-browser-acceptance.json.

The user privately reconnected after the required restart and approved proceeding with the USD 1.50 comparison ceiling. Live comparison ID: **5f1c35cfd6b245168496c4dce1ce9828**. Its completed results and deliberate Super selection are recorded in RELIABILITY_LIVE_ACCEPTANCE.md. Preparation, the capacity forecast and offline fixtures are separate from the live results.

## OpenAI candidate

The first proposed OpenAI comparison candidate is **GPT-6.1 Sol**, API model ID gpt-6.1-sol, with high reasoning through the Responses API. The [official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol) and [GPT-6 guidance](https://developers.openai.com/api/docs/guides/latest-model) support this tool-calling route. This is a proposed quality/cost comparison, not a measured advantage over Nemotron. OpenAI account access, integration and spending are not established by the Nebius connection; no OpenAI model call or integration was made in this build.

## Working agreement

“What is next?” requests an explanation of the proposed build and tasks, followed by waiting. It is not a build command. Arya's explicit “start the build” authorizes the described implementation. Keep the single 6D startup codebase and treat October 21 as a snapshot checkpoint. Engineering plots are the next visible feature expansion; this increment delivers investigation reliability and comparison controls.
