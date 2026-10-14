# One forced action-selection validation

October 14, 2026. Provider access works, but no complete live investigation has passed yet. The forced-protocol request was rejected with HTTP 400 before any accepted response. Its exact rejection cause was not retained. The corrected wire schema removes constrained-array keywords; strict evidence checks remain local. See [the measured sequence](LIVE_INTEGRATION_STATUS.md) for the compatibility inference and its limits. Increasing limits or repeating the profile matrix is not the next step.

## What the latest receipts establish

The session summary validation-20261014T111452267736Z.json records four requests. Native-no-thinking returned two accepted tool envelopes, each using 29 completion tokens. Both chose supported checks, but supplied one argument to checks that required an empty object. Neither check executed. The other two profiles returned finish_reason=stop, not the earlier truncation error. Exact extra argument values were not saved and cannot be inferred. The active configuration was correctly left unchanged.

These observations establish provider access and short native tool responses. They do not establish that thinking was disabled or that an investigation completed. The kernel findings remain independent.

## The redesigned interface

Every request now forces **one** function, select_next_action, with exactly two required fields:

    {"action": "check_force", "evidence_ids": []}

The action enum contains only unfinished applicable checks. Once all evidence exists, it contains only finish. The evidence array sent on the wire has only a string-item type; the controlled menu supplies actual recorded identifiers. Local validation requires empty evidence for checks and unique exact recorded IDs for finish. The model never supplies physics parameters. Strict local validation rejects missing/extra fields, duplicate JSON keys, unavailable actions and invented evidence before any experiment runs. Valid selections are mapped to canonical runner calls using the locked contract. A semantic mistake can receive one controlled correction; malformed envelopes remain terminal.

The request and response conversation preserves actual tool-call identifiers. Receipts record selection_protocol=forced_action_v1, wire_tool=select_next_action and source fingerprints, so the adapter is visible. The model must actually select finish; the independent audit cannot finish its investigation for it. Nebius documents explicit named function choice in [Function calling & Tools](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling).

The new session uses **only** the previously responsive native_no_thinking request profile, 2,048 output tokens, and the forced selector. There is no repeated profile matrix, transport retry, model switch or fixture fallback. The [NVIDIA Nano model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) documents the native flag; the request profile name still describes a requested setting, not measured hosted reasoning behavior.

## Private terminal command

Both constructed example contracts were acknowledged in the earlier session. Use the same folder and existing active key:

    Set-Location -LiteralPath 'C:\Users\Arya\Documents\Codex\2026-10-04\i-a\6d-startup'
    & 'C:\Users\Arya\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 tools/with_token_factory_key.py verify-live --accept-contract

Enter the key once at the hidden prompt. It stays in that process and is removed on exit. No setup, key recreation, contract re-reading or Git pull is required in this workspace.

The session must complete **both** the Euler method-limitation and force-sign-defect investigations, verify actual evidence and match independently rerun kernel findings. Only then does it atomically save the selection protocol, request profile and output ceiling in the ignored configuration. Other account, approval, price and cap fields remain unchanged. A partial result cannot install the new protocol.

Limits: **$0.10 and at most ten reserved requests**, within the existing **$5 cumulative allowance and same durable ledger**. Failed requests retain reservations; these are ceilings, not invoices. Account, transport, ledger and usage-bound failures stop the session. Every actual report and a final summary are saved in artifacts/provider-validation.

Success prints **Live end-to-end investigation completed. The validated profile is now saved locally.** A failure keeps the active configuration unchanged. Send only the final **Validation summary JSON** path; do not repeat a failed session manually.

All **223 tests passed offline**, including a schema-rejecting mock gateway, safe HTTP diagnostics and bounded wire-conversation replay with an invalid selection, one correction and actual kernel evidence for Euler, Verlet and a force defect. Independent implementation review found no blocking issue. This verifies local behavior, not live compatibility: a new completed live receipt is still required. No paid inference was run by Codex during this correction. Codex's process has no local inference credential; the hidden key entered in Arya's earlier terminal invocations is not retained.
