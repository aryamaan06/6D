# 6D — first live integration attempt and diagnostics

October 14, 2026, Asia/Calcutta. **The initial two-case live integration gate is complete.** Current model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`; existing approved cumulative allowance: $5, unchanged. Historical failures below are preserved as measured debugging history.

## Verified completion

Session `artifacts/provider-validation/validation-20261014T181514388787Z.json` completed both constructed cases and installed native_no_thinking/forced_action_v1 with a 2,048-token ceiling. Euler receipt ending `20261014T181519125190Z.json` records three accepted native responses and two experiments with method_limitation. Force-defect receipt ending `20261014T181525508833Z.json` records four accepted native responses and three experiments with defect_likely. All seven requests produced accepted native tool calls with finish_reason=stop and provider-origin IDs. There were zero protocol rejections or corrections; no content-selection adapter, fixture, profile matrix or transport retry was used.

Post-run verification checked both saved payloads, locked contracts, exact finish citations, source fingerprints against current code, installed configuration and independently rerun kernel findings. The session retained a $0.01461258 conservative reservation, not a provider invoice, within the existing cumulative $5 ledger. Existing 237 offline tests remain the development baseline; no additional paid request was made while inspecting the result. This establishes end-to-end integration for these two constructed examples. It does not establish broad model performance, thinking-off behavior, customer value, whole-vehicle coverage or mission readiness.

Initial provider troubleshooting is closed for this tested workflow. The separate project-aware browser orchestration gate also passed on October 16 after private connection: thermal completed four native tool responses and its exact fresh same-adapter recheck; unsupported GNC completed three while remaining not assessed, without an invented solver. Canonical saved records stayed unchanged. The seven requests reserved USD 0.00780588 under the existing allowance. See PROJECT_ASSISTANT_LIVE_ACCEPTANCE.md for receipts and the explanation-quality caveat. Continue product/model-quality evaluation; do not repeat either live validator without a relevant change or unresolved concern.

## What was measured

Arya's private-terminal Euler example produced an internally verified evidence receipt `artifacts/ce9ec2c95b6c9f98cb7c-20261014T072104201008Z.json`. It records one transport request attempt, zero accepted provider responses, no recorded usage/tool trace, and investigation state `failed`. The independent numerical audit passed the declared force/refinement checks and returned the expected method limitation. Those kernel findings are not proof that the model integration worked.

The durable local ledger retained a conservative $0.00132948 reservation against the $5 cap. It is not a measured provider charge; neither a failed investigation nor zero accepted responses proves no tokens were billed. The old receipt and ledger are preserved.

## Known implementation defect and correction

The old broad exception handler replaced every transport, HTTP, parsing, finish-reason and reservation-bound error with the same generic message. Consequently the actual cause of that first failure cannot be recovered from its receipt. No diagnosis such as invalid key, unavailable model, timeout or reasoning truncation is established by that record.

The corrected provider reports controlled HTTP status codes, timeout/network/TLS categories, invalid JSON/response structure, allowlisted finish reasons and usage-bound failures. It never prints remote response bodies/headers, free-form model text or arbitrary exception messages. Reservations remain durable, and there is no automatic retry. Console output distinguishes attempted requests from accepted responses.

Fifteen new offline tests cover these failure/privacy/accounting boundaries and valid tool responses. All 130 integrated tests passed after the correction. No new live request or model/endpoint/token-limit change was made by Codex during this fix.

## Classified follow-up and targeted correction

The follow-up receipt `artifacts/ce9ec2c95b6c9f98cb7c-20261014T081510132299Z.json` records one request attempt, zero accepted responses and `finish_reason=length`. The app received a completion-shaped response, but it was truncated before a complete structured tool response was accepted. The configured maximum was 1,024 output tokens. The receipt does not record how many tokens were reasoning versus visible output; do not claim that allocation was measured. This establishes the immediate truncation blocker, not successful tool integration.

The configured Nano completion limit is now **8,192 tokens**, with a **180-second request timeout** to allow the larger response to finish. The supported `max_tokens` request field is retained; no speculative reasoning-toggle parameters or model switch were added. Legacy configurations keep their defaults when optional fields are absent. The cumulative $5 approval, model/endpoint/prices and existing ledger are unchanged. At adjustment time the ledger retained $0.00199422 in conservative reservations; this remains a reservation, not an invoice.

Ten additional offline tests verify backward-compatible configuration, validated limits/timeouts, retained reservations, rejection before sending when the cap is insufficient, completion usage bounds and timeout forwarding. All **140 tests passed**. No paid call was made by Codex during this adjustment.

## Accepted live response and tool-protocol correction

The verified receipt `artifacts/ce9ec2c95b6c9f98cb7c-20261014T083917308009Z.json` records **one live request and one accepted provider response**, with 1,035 prompt tokens and 3,308 completion tokens. The larger allowance solved this request's truncation. The investigation then failed before any selected check executed because the first check had nonempty arguments. The empty trace rules out a repeated check at that point; exact extra fields were not retained and cannot be reconstructed. Independent kernel findings still show the expected Euler method limitation. Provider access is now measured; completed agent orchestration remains pending.

The runner now offers only unfinished checks and explicitly specifies their empty `{}` arguments. It offers finish only when every applicable check has recorded evidence, with the exact evidence IDs in its schema and description. A supported but invalid tool batch is rejected atomically, receives a controlled error reply, and may get **one protocol correction within at most five provider turns**. Invalid arguments never reach the physics functions; checks cannot rerun, and invented evidence cannot finish a review. Unsupported tools, malformed messages, identifier violations, transport errors and truncated completions remain terminal. A protocol correction is a separately budgeted continuation, not a transport retry or hidden fixture fallback.

Rejected calls now have a safe trace status, controlled error category and argument count, without parameter values or free-form model text. HTML distinguishes rejected calls from executed evidence. The independent final audit and contract lock still govern findings. The original receipt is preserved. The existing ledger has a $5 cap and $0.00437928 in conservative reservations at inspection; these reservations are not invoices. No live inference was run by Codex while applying this correction.

All **159 tests passed offline**, including 19 new cases covering recovery, atomic rejection, never rerunning checks, exact finish citations, message continuity, repair exhaustion, budget exhaustion before transport and truthful report rendering. An independent read-only review found no remaining blocking implementation issue. These checks establish local behavior, not a completed live investigation.

## Recurring truncation and bounded profile validation

The verified receipt `artifacts/ce9ec2c95b6c9f98cb7c-20261014T103655559051Z.json` again records one request, zero accepted responses and `finish_reason=length`, before any protocol correction or tool execution. The local limit was 8,192. That old failed-response path did not retain reported usage; no reasoning-token allocation can be reconstructed. The numerical method-limit result still comes independently from the kernel.

The previous temperature-0 request profile did not follow NVIDIA's Nano tool-calling sampling recommendation. This is a plausible contributor, not a proven cause. The new explicitly invoked session tests three request profiles, retains safe failed-response usage and requires both constructed Euler and force-defect investigations to complete with verified independent evidence before saving a profile. Hosted Nano thinking-control behavior is not assumed. It adds a $0.10/15-request session ceiling within the unchanged $5 ledger. At the latest read-only inspection the ledger retained $0.0091548 in conservative reservations, not measured charges. All 197 offline tests passed and no paid inference was run by Codex during this correction.

## Profile session and forced action redesign

The summary `artifacts/provider-validation/validation-20261014T111452267736Z.json` records four actual requests and no completed investigation. Native-no-thinking produced two accepted envelopes, each with 29 completion tokens; both selected supported checks but supplied one unexpected parameter. Trace statuses show both were rejected and no selected check executed. The other two profiles returned stop, not length. Their model prose was not accepted or retained as evidence. The active configuration was preserved. Session reservations were $0.00516966; this is not a provider invoice.

The provider now supports an explicit **forced_action_v1** protocol: one named select_next_action tool, required action enum and evidence_ids, strict local validation and visible mapping to canonical locked-input checks. No no-argument check schema is sent on that wire path. A bounded semantic correction retains matching call IDs without saving untrusted values. Finish still requires actual recorded evidence and a model selection. Receipts name the wire tool, protocol and source versions.

The next verify-live session tests only the responsive native profile with this redesigned protocol. Both actual case receipts and independent kernel evidence must pass before installing it. The session is bounded to ten requests/$0.10 within the same $5 ledger, with no matrix or model/fixture fallback. All 214 offline tests passed, including corrected wire-conversation replay for Euler, Verlet and a force defect; independent review found no blocking issue. No paid inference was run by Codex, whose process has no local credential. Actual live completion remains pending.

## Forced-protocol request rejection and schema portability

The summary `artifacts/provider-validation/validation-20261014T131555019716Z.json` and verified case receipt ending `20261014T131608213263Z.json` record one request, zero accepted responses and HTTP 400. The trace is empty and the configuration was preserved. The session retained a conservative $0.00093114 reservation, not a provider invoice. No exact rejection detail was retained by the old HTTP handler.

The sent schema included `uniqueItems`, an unsupported array keyword in [vLLM's XGrammar backend](https://docs.vllm.ai/en/stable/api/vllm/v1/structured_output/backend_xgrammar/). [Named function choice](https://docs.vllm.ai/en/stable/features/tool_calling/#named-function-calling) uses constrained structured output in vLLM. This establishes a portability defect and a leading explanation; it does not prove Nebius uses that backend or reconstruct the particular rejection. The wire evidence schema is now only a typed string array. Empty check citations, unique exact finish IDs and locked physics inputs remain enforced locally.

The HTTP handler now inspects at most 8,192 bytes of structured error JSON internally, retaining only status, allowlisted type/code/parameter and known schema-keyword mentions. Raw messages, bodies, headers, URLs, unknown values and credentials are never persisted or printed. Mentions are diagnostic clues, not asserted causes. This retains the existing no-retry and spending behavior.

All **223 tests passed offline**, including a mocked schema-rejecting gateway, actual kernel evidence through the adapted conversation, diagnostic privacy, malformed/oversized errors and retained reservations. Independent review found no blocking issue. No paid inference was run by Codex. Live compatibility remains unverified; both actual completed case receipts are still required.

## Short stop response and client receiver correction

The summary `artifacts/provider-validation/validation-20261014T180051678689Z.json` and verified case receipt ending `20261014T180053881185Z.json` record one request, stop, 1,087 prompt and 19 completion tokens. The client rejected it before inspecting the returned action. The session reservation was $0.00092808, not an invoice. No tool trace was retained and the configuration stayed unchanged. The discarded message prevents establishing its actual response format.

The [current vLLM serving implementation](https://docs.vllm.ai/en/stable/api/vllm/entrypoints/openai/chat_completion/serving/) explicitly uses stop for named tool calls, unlike automatic/required calls. Our named selector required tool_calls as the finish reason, which was a concrete client compatibility bug. This source does not prove the particular Nebius response contained a valid tool call. The receiver now permits stop only with a validated forced-action response: either a native named call, or a complete bounded two-field action/evidence selection JSON object in content. Content adaptation is explicitly our compatibility handling, not established Nebius behavior. It uses runner-origin internal IDs and the same strict action/evidence decoder. No prose, fences or JSON-substring extraction is permitted. Truncation, unknown fields, duplicate keys, unsupported actions and invented evidence cannot execute checks or finish an investigation.

Receipts retain actual response_format, finish_reason and call_id_origin; saved reports check their consistency. Failed responses retain only controlled outer shape/count/presence facts alongside existing safe diagnostics. No raw text or reasoning is saved. All **237 offline tests passed**, including four complete conversations (Euler and force defect in both response formats), mixed formats, semantic correction, strict failure cases, persisted provenance and refusal to install offline results. Independent review found no blocker. No paid inference was run by Codex. Actual live completion remains pending.

That pending validation subsequently completed, as recorded at the top of this document. [LIVE_VALIDATION.md](LIVE_VALIDATION.md) remains the setup/acceptance reference for new environments or relevant future changes; no repeat is currently required.

Primary API references: [Nebius chat completion parameters](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion), [function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling), [Nano recipe](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-nano-30b.md) and [NVIDIA's Nano model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16). LIVE_VALIDATION.md distinguishes documented parameter shapes from unmeasured compatibility on this hosted Nano deployment.
