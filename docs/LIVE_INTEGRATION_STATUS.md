# 6D — first live integration attempt and diagnostics

October 14, 2026, Asia/Calcutta. Live integration is not yet completed. Current model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`; existing approved cumulative allowance: $5, unchanged.

## What was measured

Arya's private-terminal Euler example produced an internally verified evidence receipt `artifacts/ce9ec2c95b6c9f98cb7c-20261014T072104201008Z.json`. It records one transport request attempt, zero accepted provider responses, no recorded usage/tool trace, and investigation state `failed`. The independent numerical audit passed the declared force/refinement checks and returned the expected method limitation. Those kernel findings are not proof that the model integration worked.

The durable local ledger retained a conservative $0.00132948 reservation against the $5 cap. It is not a measured provider charge; neither a failed investigation nor zero accepted responses proves no tokens were billed. The old receipt and ledger are preserved.

## Known implementation defect and correction

The old broad exception handler replaced every transport, HTTP, parsing, finish-reason and reservation-bound error with the same generic message. Consequently the actual cause of that first failure cannot be recovered from its receipt. No diagnosis such as invalid key, unavailable model, timeout or reasoning truncation is established by that record.

The corrected provider reports controlled HTTP status codes, timeout/network/TLS categories, invalid JSON/response structure, allowlisted finish reasons and usage-bound failures. It never prints remote response bodies/headers, free-form model text or arbitrary exception messages. Reservations remain durable, and there is no automatic retry. Console output distinguishes attempted requests from accepted responses.

Fifteen new offline tests cover these failure/privacy/accounting boundaries and valid tool responses. All 130 integrated tests passed after the correction. No new live request or model/endpoint/token-limit change was made by Codex during this fix.

## Next step

Arya runs the same private-key investigation command once in the existing workspace, following TODAY_TASKS.md. That uses the remaining existing allowance and should produce a classified error or a completed receipt. The key is entered locally through the hidden prompt; no key is needed in this chat. Codex then applies any specific correction supported by the new evidence. Preserve the ledger and report path; no repeated blind retries.

Primary API references: [Nebius function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling) and [Nano recipe](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-nano-30b.md). NVIDIA documents reasoning controls for [Nano](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-nano-30b-a3b), but their support on Arya's Nebius endpoint has not been established; no such parameter was added speculatively.
