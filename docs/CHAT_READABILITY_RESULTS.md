# Chat readability and model-check correction

October 27, 2026. Local application: **http://127.0.0.1:8768/**. Current implementation build **cbd5b64fe0be**. [Acceptance](CHAT_READABILITY_ACCEPTANCE.md) · [Prospective live plan](CHAT_READABILITY_LIVE_PLAN.md).

![Expanded conversation with explicit model selection](images/6d-current-workspace.png)

*Fresh capture of the actual interface on an isolated constructed browser fixture. The visible answer is supplied by an offline test provider; it is not a live Nemotron response or customer data.*

## Interface changes

New chats start at **Choose a model**, including when old browser storage contains a Super preference. Send requires an explicit choice. The options give task guidance: **Nano — Quick explanations**, **Super — Everyday review**, **Ultra — Deeper reasoning**. A selected model is retained within the active saved context; New conversation clears the choice. Historical answers keep their actual model identity. The server's legacy configuration default is unchanged and is never silently substituted by the ordinary chat UI.

**Expand / Restore size** changes the existing native dialog without remounting its transcript, composer or local attachment. The regular window is wider, both services use stable window geometry, the conversation has a substantially larger reading area and evidence/settings remain optional. Model and scope share a compact control row. Small viewports and explicitly expanded technical/image content retain scroll access to all controls.

An explicit disclosure activation temporarily disables native anchoring and preserves its summary position through layout. Pointer and Enter/Space behavior, focus, exact mounted draft inputs, existing style priorities and manual scroll interruption remain intact. Both ordinary workspace details and conversation evidence are covered. This does not replace intentional navigation or force the reader to the bottom.

## Investigation correction

The requirement adapter had retained generation-only finish-summary regex/minimum-length constraints similar to those implicated in an earlier Super compatibility failure. They were removed from constrained generation; local summary length, words-only, numerical/status/direction/source, citation and readiness acceptance checks remain enabled. Finish citations are bounded to the captured set and still checked exactly locally.

The provider-only projection also omits repeated witness placeholders, duplicated provenance, before/after records already represented by the source-derived change context and the identical successful recheck artifact. Full captured evidence remains in the receipt. Required reads and fresh recheck, numerical calculations, output ceiling, provider models, per-job limits and cumulative allowance are unchanged. A constructed final-request measurement fell **80,006 → 46,887 UTF-8 bytes**, a **41.4% reduction**; this is payload evidence, not a model-quality benchmark.

## Initial authorized live batch

Arya approved at most six jobs / 36 requests / USD1.30 in reservations on the constructed R3 burnout-altitude evidence, with two identical questions per model and no automatic retries. [Sanitized retained result](validation/CHAT_READABILITY_LIVE_BATCH1.json).

| Model | Observed first turn | Requests | Reservation |
| --- | --- | --- | --- |
| Nano | Complete final action, explanation rejected locally | 5 | USD0.01388226 |
| Super | Complete final action, explanation rejected locally | 5 | USD0.06633330 |
| Ultra | Complete final action, explanation rejected locally | 5 | USD0.22111100 |

All three completed their final native-tool response, so the earlier output-limit failure did not recur in these cases. **No final answer was accepted and no follow-up was sent.** Total **USD0.30132656** is conservative reservation accounting, not billed cost. These failed receipts remain failed and unchanged.

Investigation found a guard defect: descriptions of **constant thrust during one modeled burn** were treated as claims that thrust was unchanged **between saved revisions**. The correction makes that narrow distinction while retaining checks for explicit revision equality, opposite directions, unchanged claims and separate subject/clause assertions. Twenty-four minimal synthetic examples cover both legitimate assumptions and genuine contradictions. Offline reassessment of the original text removes that false direction flag for all three models; it does not relabel their historical receipts as passed.

Ultra also used **RK4**, which contains a digit and violates the existing qualitative prose contract. That independent guard remains intact.

## Second batch and subsequent correction

Arya separately approved a fresh corrected batch capped at USD0.99, with both initial batches kept below USD1.30. [Sanitized second result](validation/CHAT_READABILITY_LIVE_BATCH2.json). Nano and Super each completed two turns with the correct model-local captured parent. Ultra's first response was rejected; no Ultra follow-up ran. This phase used **25 requests and USD0.38781342 reserved**. Both phases together reserved **USD0.68913998**; no automatic retries or other-service calls occurred.

Manual development review distinguished acceptance from usefulness: Nano repeated the earlier definition without the requested concrete next check. Super gave a relevant assumption-review action but remained repetitive. Ultra's complete answer included a numeric coast duration and another legitimate within-model constant-thrust description that the direction guard misread. These observations are not an independent human evaluation.

The temporal guard now also recognizes explicit within-model descriptions and stated-assumption headings, with **32 minimal synthetic examples** retaining genuine contradiction coverage. Original failed records remain unchanged; the numeric-literal policy is not relaxed. The modern system prompt is now independent of the older generic report checklist. It prioritizes the active question, short plain-language answers, a specific next action when requested, and existing evidence/tool/numerical boundaries. Each action boundary repeats the **current question as user data**, so the prior conversation cannot silently replace it. Legacy-policy prompting remains unchanged.

## Third batch: completion did not establish answer quality

With a separately approved USD0.90 ceiling, all six first/follow-up jobs completed on build 9e05437138d3. Thirty requests reserved **USD0.55920630**. [Retained third result](validation/CHAT_READABILITY_LIVE_BATCH3.json). This is a protocol success, not six clean semantic-quality passes: Nano again omitted the requested next action, and Super's follow-up asserted that sufficient height ensured obstacle clearance and entry into space. The bounded burnout-altitude check establishes neither outcome. Ultra gave a relevant explanation and follow-up but was more verbose than requested.

The completed Super receipt is retained unchanged. A separate offline reassessment now rejects its explicit unsupported mission assurance using the existing readiness/guarantee blocking policy. Seventeen additional literal cases distinguish such assurances from denials, questions, hypotheticals and proposed independent checks. The final action menu also explicitly identifies next-check requests and asks for one applicable action and its rationale rather than repeating an earlier definition. This changes response guidance, not tools, permissions, evidence, calculations or thresholds.

All three phases together reserved **USD1.24834628**. Each phase required its own explicit approval; none automatically retried a failed or poor answer. No image pixels, Tavily searches or LangSmith uploads were sent.

## Current-source verification: six completed useful scoped turns

After a separate approval capped at USD0.90, build **cbd5b64fe0be** completed both questions for every model. Each follow-up captured only its own model's accepted first answer in the same saved evidence context. [Sanitized current-source result](validation/CHAT_READABILITY_LIVE_BATCH4.json).

| Model | Completed jobs | Follow-up observation | Reservation for both turns |
| --- | --- | --- | --- |
| Nano | 2/2 | Now names source review and independent checks of thrust, mass flow and drag. Still repetitive; internal-consistency wording is loose. | USD0.02692098 |
| Super | 2/2 | Concise; targets thrust provenance and retains single-axis/model limits. The earlier space-entry assurance did not recur. | USD0.12659550 |
| Ultra | 2/2 | Names input/applicability and saved-event checks. Still verbose; its phone-battery analogy is imperfect. | USD0.41302800 |

This phase used **30 requests and USD0.56654448 in reservations**. Across all four approved phases: **20 jobs, 100 requests and USD1.81489076 reserved**. The last approved combined ceiling was USD2.14834628. There were no automatic retries, model fallbacks, image transfers, Tavily searches or LangSmith uploads. Reservations are not confirmed billed usage.

Development review observed useful definitions and relevant next checks in these six turns. It does not establish perfect prose, broad semantic accuracy or independent human qualification. The exhaustion-based definition fits this supplied model, not every possible commanded engine shutdown. Passing a height criterion and reproducing a calculation remain separate evidence. All prior failures and manual-quality findings remain visible in their own dated records.

## Verification and preservation

The final scoped Python run passed **226 methods**, zero skips/errors. **39 component checks** passed. Browser coverage passed **65 groups**: seven current chat, six native-disclosure regressions, 15 usability/reference, 27 navigation/drafts and ten exact-context handoff groups. The captured disclosure regression moved the summary from 140px to −876px without the fix; with it the summary stayed at 140px. All **39 JavaScript files** parse and all **64 Python runtime sources** satisfy canonical LF policy. These are scoped runs, not a fresh full-suite or independent physics/semantic validation. No fixture response is live inference.

The original automatic-approval-review usage-limit interruption and the initial stale fixture selectors/module invocation/socket-permission failures remain part of the working record; their affected final runs pass separately and failed runs are not counted as green.

The owner audit retains **all 29 original investigation rows plus the 20 authorized additions**. Of 28 table/file checks, 26 match exactly; only investigation rows and their matching USD1.81489076 ledger reservation differ. Every other table, all three encrypted credentials, both configurations, the cumulative allowance/server default and saved numerical evidence/source library are unchanged. All remembered services restored. [Machine-readable checks](validation/CHAT_READABILITY_CHECKS.json).

The current-source six-turn path is demonstrated. No broad semantic qualification, new physics, Lightning integration, project deletion or public deployment is claimed. The README/current screenshot/status guide now foreground current behavior and link historical records separately.
