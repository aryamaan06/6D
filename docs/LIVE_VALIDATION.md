# One private live-validation session

October 14, 2026. Provider access has been demonstrated, but no complete live investigation has passed yet. Repeating the earlier investigate command is no longer the recommended troubleshooting path.

## What changed

The latest receipt again reports `finish_reason=length` with the configured 8,192-token allowance. Its old error path discarded valid usage, so the receipt cannot establish how many tokens were reasoning. Increasing the limit alone did not establish reliability. Previous requests used temperature 0 with unspecified thinking behavior. NVIDIA recommends temperature 0.6 / top_p 0.95 for Nano tool calling; this mismatch is a plausible contributor, not a proven diagnosis. [NVIDIA Nano model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16)

The new explicitly invoked session tests three request profiles using the same Nano model, endpoint and approved prices:

| Order | Profile | Requested settings | Output ceiling |
| --- | --- | --- | --- |
| 1 | `nebius_no_reasoning` | temperature 0, reasoning_effort `none` | 2,048 |
| 2 | `native_no_thinking` | temperature 0, top-level chat_template_kwargs enable_thinking false | 2,048 |
| 3 | `tool_sampling` | temperature 0.6, top_p 0.95 | 8,192 |

Nebius lists reasoning_effort `none` in its [API reference](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion). NVIDIA documents the native flag for Nano under vLLM, and a [Nebius-owned hosted verification](https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory-deprecation-verification.md) demonstrates it for Lightning. Neither establishes behavior on this exact hosted Nano deployment. These are labelled compatibility experiments; a completed run does not itself prove thinking was disabled. Raw HTTP uses a top-level native field; `extra_body` in an OpenAI SDK example is a merge argument.

## One terminal sequence

The Euler contract was reviewed earlier. Display the second constructed example's contract, then start the session:

```powershell
Set-Location -LiteralPath 'C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup'
$sixdPython = 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $sixdPython -X utf8 run.py contract --case force_sign_error
& $sixdPython -X utf8 tools/with_token_factory_key.py verify-live --accept-contract
```

The displayed contract applies only to a constructed numerical example. The deliberately defective candidate must produce supported defect evidence; it is not a real mission. Enter the existing key once at the hidden prompt. It stays in this process and is removed when the helper exits. No key, account setup, package installation or Git pull is needed in this chat.

The session prints profile/case progress. Allow it to finish; individual requests allow up to 180 seconds. It stops at the first profile that completes **both** the Euler method-limitation and force-sign-defect investigations, verifies their recorded evidence, and matches independently rerun kernel findings. Only then does it atomically save that profile and output ceiling in the ignored local configuration. Every other account, approval, price and cap field is preserved. Partial success cannot change configuration.

## Limits and truthful outcomes

- At most three profiles, fifteen reserved requests and $0.10 in conservative session reservations, all within the existing cumulative $5 allowance and same durable ledger.
- Every request, including one controlled tool-format correction, reserves before sending. Failed requests retain reservations; these are ceilings, not provider invoices.
- Account, network, TLS, timeout, ledger and usage-bound failures stop the whole session. Profile incompatibility may advance to a visibly named next profile. No transport retry, model switch or fixture fallback occurs.
- Each actual report is retained in `artifacts/provider-validation`. Failed-response diagnostics keep only controlled finish reasons, validated token counts, configured limit and profile; reasoning text and parameter values are excluded.
- The final summary retains actual outcomes and source/profile provenance. A fixture, independent kernel headline or accepted HTTP response alone cannot pass the session.

Success prints **`Live end-to-end investigation completed. The validated profile is now saved locally.`** Failure preserves the active configuration and prints no success claim. Send the **Validation summary JSON** path from either outcome; Codex can inspect all included receipts without repeated output copying or receiving the key. Do not repeat a failed session manually.

All **197 tests passed offline**, covering profile payloads, metadata privacy, key cleanup, session/global ceilings, fatal billing stops, partial failures and the two-case acceptance gate. This is local verification, not evidence that the new session has already succeeded on Nebius. No paid inference was run by Codex during this correction.
