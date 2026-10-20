# 6D Token Factory connection and accounting

Updated October 16, 2026, Asia/Calcutta. The existing account configuration uses `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Nebius Token Factory. Arya confirmed an active `6d-local-development` key and USD 29.50 balance on October 14; that historical balance is not a current account query. The unchanged authorization is USD 5 cumulative inference from existing balance only, with no additional card spending. No replacement key or new approval is needed for this setup.

## Connect through the browser

Open http://127.0.0.1:8768/ and refresh after a delivery. If needed, start it with **Open-6D.cmd** from Windows File Explorer; see OPEN_6D.md.

1. Choose **Connect AI**. Paste the existing key privately into the password field and choose **Connect key**. Do not share it in chat, put it in source files or include it in a question.
2. Select a saved requirement whose current revision has calculation evidence. Choose **Investigate** and enter a bounded engineering question.
3. Review the scope notice, then choose **Start live investigation**. This sends the question and scoped requirement/model/input records to NVIDIA Nemotron Nano on Nebius and consumes the existing allowance.
4. Inspect actual activity, the canonical finding, separately labelled AI interpretation and evidence citations. Download the investigation JSON if useful.
5. Choose **Disconnect key** in the connection settings when finished. Restarting the local server also clears a key entered through this dialog.

Connecting validates local configuration only. It does not authenticate remotely or start an inference call. Opening the app, selecting a requirement, refreshing and reconnecting never start jobs automatically. The password field is cleared after submission; the key stays in server memory, not browser storage, project records, exports or the nonsecret configuration file. Local calculations and saved-history inspection work without a key.

A server may also inherit NEBIUS_API_KEY from its launch environment. Environment variables set in another terminal do not appear retroactively in the running server. The browser connection is the current recommended founder workflow; repeated terminal/profile experiments are unnecessary.

## Separate acceptance gates

The October 14 orbital integration passed on two constructed cases: Euler method limitation and force defect, with seven actual native responses and independently matching orbital kernel evidence. The installed local settings are native_no_thinking, forced_action_v1 and a 2,048-token completion ceiling. That pass is preserved in LIVE_INTEGRATION_STATUS.md; it does not establish general model quality or whole-mission validity.

The October 16 project Assistant completed its first two actual live investigations after private connection: thermal (four native responses with matching fresh recheck) and unsupported control (three native responses, status still Not assessed, no invented solver). This passes the tested project orchestration gate, separately from the earlier orbital pass. The control prose has a documented ambiguity: insufficient evidence cannot establish satisfaction; it does not prove a physically impossible requirement. See [project live acceptance](PROJECT_ASSISTANT_LIVE_ACCEPTANCE.md). Offline wire/API/browser checks still cover bounded tools, revision locks, citations, memory-only connection, persisted jobs and accounting. No repeat of this initial gate is needed absent a relevant change.

The browser shows actual request attempts and accepted live responses separately. A connection indicator is not a successful remote response, and an accepted response alone is not a completed investigation. A completed live project receipt must identify its selected saved revision, review digest, model, actual tool activity, citations and fresh recheck where supported.

## What the Assistant can do

The project agent can read one selected requirement, its bound model and saved evidence, inspect explicitly recorded revision differences, request one fresh calculation with the maintained adapter and finish with exact evidence IDs and a bounded explanation. The fresh recheck tests reproducibility using the same adapter; it is not independent physical validation. The canonical engineering finding cannot be changed by model text. Unsupported models stay unassessed even if the agent finishes explaining them.

Tools cannot edit inputs, execute arbitrary code, modify requirements, supply new physics values, authorize launch or silently expand scope. Project strings, source labels, questions and provider prose are untrusted data. Valid model explanations are stored as **AI interpretation**, separate from the deterministic finding.

Jobs persist in .local/workspace.sqlite3 with actual progress, evidence and revision/review provenance. A server restart marks unfinished work failed and preserves partial activity; it does not resubmit it. Disconnect blocks later request reservations, while a request already reserved/sent can still be in flight. Check saved status before deciding on another explicit start. No transport retry, automatic job retry, profile matrix, model fallback or fixture fallback runs in this workflow.

## Provider configuration

The nonsecret .local/token-factory.json records the exact routing ID, approved spending reference, price ceilings, endpoint and explicit request settings. It is separate from the private key. `docs/token-factory.example.json` remains an intentionally disabled template for other installations. The adapter does not load .env files.

Supported HTTPS endpoints are `https://api.tokenfactory.nebius.com/v1/` and `https://api.tokenfactory.us-central1.nebius.com/v1/`. Requests use `/chat/completions`, structured messages and one named `select_next_action` tool. The project adapter validates the current action menu and exact evidence IDs locally. The default orbital action adapter is unchanged. Redirects are rejected so bearer credentials are not forwarded elsewhere.

The current profile requests temperature zero and top-level chat_template_kwargs with enable_thinking false. This is a requested hosted setting, not proof of measured reasoning behavior. Forced named calls are accepted with stop or tool_calls after strict envelope validation; exact bounded content-selection JSON is accepted only with stop and no tool calls. Response format and call-ID origin remain explicit. Arbitrary/fenced prose, extra fields, fabricated citations, duplicate JSON fields and unavailable actions are rejected.

Remote errors retain only controlled categories and allowlisted diagnostics, never raw bodies, headers, arbitrary messages or private exception text. Failed responses retain their reservation. Safe token counts may be recorded when available; missing usage does not establish zero billing. A validated stronger model or automatic model router is not implemented. See MODEL_STRATEGY.md for the proposed evaluation.

## Existing allowance and per-job bounds

.local/budget.sqlite3 atomically reserves allowance before every request across runs/processes. All old and new requests share the existing USD 5 cumulative approval; changing a model or starting another job does not create a new allowance. Reservations use request UTF-8 bytes plus framing as a conservative input-token bound, the maximum output tokens and verified price ceilings. They are never refunded automatically, including after failure or timeout. Exhaustion blocks before transport. Changing the approval ID/cap on the existing ledger is rejected.

Each browser project investigation has a further ceiling of six request reservations and USD 0.10 conservatively reserved. These bounds sit inside the cumulative USD 5 allowance; they are not extra spending approval. Do not delete/reset the ledger, create a second ledger or change prices/caps to regain room. No additional card charge is authorized.

These are conservative application controls, not a provider invoice or a provider-side card limit. Other API clients, taxes/fees, deleted ledgers, changed provider prices and incorrect ceilings are outside this application bound. The provider account's paid-usage preference does not authorize this app to exceed Arya's allowance.

Nano's public rates were checked October 16 on the [official Nebius Nemotron overview](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference): USD 0.06 per million input tokens and USD 0.24 per million output tokens, matching Arya's earlier console report and the existing local ceilings. This is dated metadata, not a new remote account/model-access test. No configuration or routing policy changed during that check.

## Preserved offline and CLI workflows

The workspace's deterministic calculations need no credential or paid inference. The preserved orbital workflow also supports an explicitly scripted offline investigation:

```console
python run.py investigate --case euler_method_limit --provider fixture --accept-contract
```

It records provider fixture and zero live calls; numerical evidence is freshly calculated. Injected HTTP transports identify themselves as offline_transport_fixture and do not meet a live gate. Existing private CLI helpers remain for developer reproduction and the earlier orbital workflow, but are not required for the browser steps above.

.local/, .env files, generated reports/work and caches are excluded by Git ignore rules. These rules do not replace reviewing staged/public files for private material. Keep the key and spending ledger local and out of Git. Local unsigned digests establish internal consistency, not authenticated security or team approval.

## Primary references

- [Nebius function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling), reviewed October 16 for the project integration.
- [NVIDIA Nano model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) and [NVIDIA Nemotron Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/), reviewed for the selected model; no weights are bundled in 6D.
- [Official Nebius Nemotron overview and rates](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference), checked October 16.
- The original two-case receipts and narrow claim boundaries remain in LIVE_INTEGRATION_STATUS.md; historical debugging commands are not the current founder setup sequence.
