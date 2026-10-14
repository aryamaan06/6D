# 6D Token Factory setup

Updated October 14, 2026, Asia/Calcutta. Arya confirmed $29.50 and an active `6d-local-development` key, exact routing ID `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, and console prices $0.06 input / $0.24 output per million tokens. The selected model's official license and tool-calling API documentation were reviewed. The existing approval is $5 cumulative initial inference from current balance only; no additional card spending. Nonsecret `.local/token-factory.json` is configured. After a generic first failure, the classified follow-up confirmed output truncation at 1,024 tokens. The local Nano configuration now permits 8,192 completion tokens and a 180-second request timeout. Successful live tool integration is still pending. [Exact Windows commands](TODAY_TASKS.md) are ready for Arya's private terminal, and [live status](LIVE_INTEGRATION_STATUS.md) records the receipts and targeted correction.

## Offline workflow now available

No credentials, inference credits or third-party Python packages are needed:

```console
python run.py provider-status
python run.py contract --case euler_method_limit
python run.py investigate --case euler_method_limit --provider fixture --accept-contract
python run.py serve
```

In the local UI, select **Scripted tool investigation · no model inference**. The fixture selects force, refinement, applicable Verlet reversibility and finish tools. The Euler example requires the first two checks only. The numerical results are freshly computed by the kernel, not fixture measurements. Reports label the provider `fixture` and record zero live calls. An injected mock HTTP transport labels itself `offline_transport_fixture`.

The live adapter shares the same provider interface. It uses standard-library HTTPS, OpenAI-style messages/tools and `/v1/chat/completions`. Current Nebius documentation lists `tool_choice: auto` and explicit function selection; this adapter uses `auto` and rejects responses without structured tool calls. Live API compatibility and model behavior remain to be tested after the gates below are satisfied.

## Prepared configuration and remaining private step

The exact account routing ID above is used, rather than the display name `Nemotron-3-Nano-30B-A3B`. The global base URL is `https://api.tokenfactory.nebius.com/v1/`. The $5 cap and user-confirmed prices are recorded with the approval reference `arya-approved-initial-tests-usd5-existing-balance`. The three verification flags reflect Arya's account report, the official license review, and the already-given spending approval; they do not claim a remote test.

The [NVIDIA model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) links the [NVIDIA Nemotron Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/), reviewed October 14. No model weights are bundled in 6D. The [Nebius function-calling documentation](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling) documents structured tool calls. Price ceilings use Arya's current console values, not a claim that a pricing page was successfully fetched. Recheck prices before a later testing phase if they change.

No replacement key, renewed $5 approval or cloud deployment is needed. After the profile matrix isolated empty-argument tool failures, the recommended check is the one-entry **verify-live** session in [LIVE_VALIDATION.md](LIVE_VALIDATION.md). It now tests one forced action-selection protocol on the previously responsive native profile, under $0.10/ten reserved requests within the existing $5 ledger. It installs the protocol only after two real completed investigations with verified independent evidence. `docs/token-factory.example.json` remains an intentionally disabled template for other installations.

Supported endpoints are `https://api.tokenfactory.nebius.com/v1` and `https://api.tokenfactory.us-central1.nebius.com/v1`. Redirects are rejected rather than forwarding a credential. The adapter does not load `.env` files.

In your own PowerShell terminal, use the helper rather than placing a key in a command or file. It asks privately, keeps the key in its own process environment and writes no key file. Its default command only inspects local configuration and makes no network request:

```console
python tools/with_token_factory_key.py provider-status
```

Nothing appears while you type/paste the key; press Enter when finished. With the prepared configuration, expect `configured: true` and the exact model routing ID. This command does not authenticate remotely. Use the same helper with `investigate --case euler_method_limit --provider token-factory --accept-contract` for the authorized first live test; enter the active key again privately.

Alternatively, use a session environment variable:

```powershell
$sixdSecret = Read-Host 'Token Factory API key (local only)' -AsSecureString
$sixdCredential = [System.Management.Automation.PSCredential]::new('6d', $sixdSecret)
$env:NEBIUS_API_KEY = $sixdCredential.GetNetworkCredential().Password
python run.py provider-status
```

`provider-status` is local and makes no network call. A configured result means local gates are present, not that authentication or credits have been remotely validated. Environment variables set in another terminal do not retroactively appear in the running Codex process; run the gated live command from the configured terminal. Do not print the environment variable.

## First authorized live investigation

The account/model/license/pricing and spending configuration are prepared. Review the constructed example contract first with `python run.py contract --case euler_method_limit`, then use the private helper:

```console
python tools/with_token_factory_key.py investigate --case euler_method_limit --provider token-factory --accept-contract
```

A sequential Euler investigation ordinarily needs three completions; a model may select both checks in one turn. The runner now has a hard limit of five turns, including at most one correction for an invalid supported tool batch. The configured Nano completion limit is 8,192 tokens with a 180-second request timeout, increased after a measured truncation failure. A full investigation can take several minutes. Optional configuration defaults remain 1,024 tokens/45 seconds for older installations; validated maximums are 8,192 tokens/180 seconds. Only unfinished checks are offered; finish is offered after all evidence exists, and a singleton tool is selected explicitly using the documented function-choice format. Invalid check parameters are never executed: controlled tool feedback permits one budgeted correction. Unsupported tools, malformed messages, repeated identifiers, truncation, transport failures and exhausted repair allowance stop the investigation. No transport retry or fixture fallback occurs. Every continuation reserves against the same durable $5 cap. The kernel still produces a separate supported numerical audit, while a stopped investigation remains failed/incomplete. Errors identify controlled categories without printing response bodies, headers, parameter values or private exception text.

The latest private live receipt confirms provider access and one accepted response; its first check incorrectly contained parameters and the previous runner stopped. The corrected tool conversation is tested offline before the next private check. An accepted provider response and a completed investigation are distinct outcomes; see LIVE_INTEGRATION_STATUS.md for the measured sequence.

Confirm `model_mode: live_token_factory`, completed investigation, positive `live_model_calls`, actual tool trace and token usage. `live_model_calls` counts accepted provider responses; `live_request_attempts` separately counts transport attempts. Zero accepted responses does not establish zero billing. Valid token counts from rejected completions are now recorded separately in `failed_provider_response`, including reported reasoning-token counts when available; absence remains unknown. No reasoning text is saved. Preserve the JSON/HTML as the receipt. A successful HTTP-shaped mock does not meet this gate. The local UI can inspect live reports created by CLI, but its run endpoints currently expose only deterministic and fixture execution.

## Explicit request profiles

`inference_profile` defaults to `tool_sampling` for legacy configurations. It uses NVIDIA's recommended Nano tool-calling sampling pair (temperature 0.6 / top_p 0.95). Supported compatibility settings also include `nebius_no_reasoning` (temperature 0, reasoning_effort none) and `native_no_thinking` (temperature 0, top-level chat_template_kwargs enable_thinking false). The current explicit validator requests only native_no_thinking with forced_action_v1; it no longer repeats the historical profile matrix. These are labelled hosted compatibility requests, not established Nano behavior. Never claim the profile name proves reasoning was disabled. No literal nested SDK `extra_body` field is sent. [Profile references and limits](LIVE_VALIDATION.md)

`selection_protocol` defaults to `native_tools_v1` for backward compatibility. The new explicit `forced_action_v1` protocol always calls select_next_action with required action/evidence_ids rather than exposing empty-argument checks. Only validated selections are mapped to the kernel's canonical interface. The action/evidence menu changes after actual checks; parameters, extra fields, duplicate JSON keys and fabricated IDs are rejected. Conversation IDs remain matched and the adapter's provenance is recorded. The verification session requests this protocol with native_no_thinking but does not persist it until both live cases pass.

The wire evidence schema is a plain typed string array; strict citation constraints are checked locally, avoiding unsupported constrained-decoder array keywords. HTTP errors are inspected only as bounded structured JSON and retain allowlisted status/type/code/parameter and schema-keyword mentions. Raw remote bodies, messages, headers and unknown values are never saved or printed. Mentions are clues, not confirmed causes.

All 223 development tests passed offline after the correction. No completed live session is claimed until the two-case validation actually succeeds. A failed session retains the prior active configuration, all reports and previous budget reservations. Account/transport/billing-bound failures stop the session. No profile matrix, model switch, transport retry or fixture fallback is run by the validator.

## Budget accounting

`.local/budget.sqlite3` atomically reserves allowance before each request, across runs/processes. Reservations use request UTF-8 bytes plus a framing allowance as a conservative input-token bound, the maximum output tokens and verified price ceilings. Reservations are never refunded automatically, including after a timeout or failed response. Exhaustion blocks before sending. Changing the approval ID or cap on an existing ledger is rejected.

This is a conservative application allowance, not a provider invoice. It covers requests through this adapter; other API clients, account taxes/fees, deleted ledgers and incorrect price ceilings are outside it. Verify provider-side billing/limits where available, and review actual usage before changing the allowance. Do not delete/reset the ledger to regain spending room. Approval changes require explicit review.

`.local/`, `.env*`, generated work and reports are excluded by `.gitignore`. This directory is now a Git repository connected to Arya's private `aryamaan06/6D` repository. Ignore rules do not replace reviewing staged files and the eventual public package for secrets. Keep the key in the process environment, separately from the JSON configuration. The private key and persistent spending ledger stay local and are not backed up through Git.

Clear the key from the terminal when finished:

```powershell
Remove-Item Env:NEBIUS_API_KEY
$sixdSecret.Dispose()
$sixdCredential = $null
```

## Evidence boundaries

The model selects supported experiments and cites their evidence IDs. It cannot provide a replacement verdict, edit a contract, execute arbitrary code, patch an adapter or add unsupported physics. Free-form model text is discarded. The report summary and engineering finding come from the deterministic kernel.

Selected checks run against the locked contract; a mandatory full audit then independently reruns and compares those measurements. This deliberately favors conservative coverage in the first bounded increment. It is not yet proof of adaptive investigation value over directly running the applicable deterministic checks.

Reports retain units, reference frame, assumptions, source fingerprints and eight explicit exclusions. Numerical reproduction reruns the matching kernel locally; it does not promise to reproduce a nondeterministic provider transcript. An inconclusive contract never invokes the provider.

Primary references: [Quickstart](https://docs.tokenfactory.nebius.com/quickstart) and [billing](https://docs.tokenfactory.nebius.com/other-capabilities/billing-new), checked October 10; [function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling), selected model card and license checked October 14.
