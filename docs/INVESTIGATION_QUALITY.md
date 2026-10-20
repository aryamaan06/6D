# Investigation quality and model comparison

October 16, 2026, Asia/Calcutta. The milestone extends the same 6D workspace and preserves its engineering workflow and cumulative USD 5 allowance.

## Implemented

- The Assistant presents the saved canonical finding, evidence-based review actions, missing information and model limits before the original AI prose. Review actions reference JSON Pointer paths in the exact saved review and captured evidence IDs. They are engineering review suggestions, not independently established new results.
- Prompts distinguish an unassessed requirement from an impossible or failed design, and ask for concrete checks supported by the available records. Limited deterministic checks flag known risky wording, contradictory status, missing citations and unmatched literal quantities. These checks can miss mistakes or flag acceptable wording; they do not prove semantic correctness.
- Existing completed investigations receive read-only guidance from their matching historical review. The original summary, saved investigation digest and project/calculation records are not rewritten. New investigation receipts record guidance and explanation checks with the run.
- A comparison service prepares six independently checked constructed cases: thermal criterion met, criterion exceeded, unsupported control, invalid heat unit, limit-only revision and a held-out drag variation. Each model receives identical initial evidence, question, tools and common settings. Subsequent tool histories can differ because model choices differ.
- Nano, Super and Ultra are evaluated under native_no_thinking / forced_action_v1 with a 2,048-token output ceiling. This compares compatibility and quality under the existing common configuration; it is not a claim that this is each model's individually optimized sampling profile.
- An explicit batch has a USD 0.75 conservative reservation ceiling and 90 total request reservations, with the existing six-request/USD 0.10 per-case ceiling and the existing cumulative USD 5 ledger. Failures retain reservations. No retries, fixture fallback, silent model switching or ledger reset. A candidate's failed investigation stops its remaining cases. Refreshing, opening status and connecting a key never start inference.
- Connection settings show actual comparison progress/results and link to its saved JSON. Completion of a batch means the evaluation finished recording outcomes, not that all models passed.

## Selection gate

Nano remains the established default. Stronger models require a complete identical-pack live result, all workflow/citation/provenance gates, and a manual semantic review showing a useful paired benefit over Nano. Keyword checks or model size alone cannot justify selection. The eligibility helper returns a review decision and cannot activate a model. Production activation is a separate deliberate change after results justify it; no automatic router is installed.

The manual-review record uses sixd.model-manual-review.v1 and binds report_digest, plan_digest, candidate_id, reviewer, reviewed_at, all reviewed_case_ids, per-case judgments (canonical_status_correct, claims_supported, next_steps_useful, notes), no_critical_unsupported_claims, and paired_benefit (baseline_candidate_id nano, demonstrated, case_ids, rationale). Constructed cases are an initial screen, not a broad engineering benchmark or independent specialist validation.

## Authorization and live status

Arya initially deferred paid calls, then explicitly approved “Run a small comparison batch now.” That authorizes one capped batch within the existing allowance, after offline acceptance. A server restart clears its private memory-only connection; if disconnected, Arya needs to reconnect once through Connect AI. Codex owns starting and inspecting the batch; no terminal command or key in chat is required. Live results must be recorded in a separate dated acceptance receipt. Preparation and offline fixtures are not evidence of actual comparative model performance.

Arya reports Nebius credits expire in a few days; the exact expiry is unconfirmed. Prioritize useful accepted evaluation work in the next chats while retaining the allowance. No automatic future spending or balance exhaustion is authorized.

## Metadata checked October 16

The founder's October 15 account screenshots match current [Nebius family pricing](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference): Nano USD 0.06/M input and 0.24/M output; Super 0.30/0.90; Ultra 1.00/3.00. Exact routing IDs are retained in model_evaluation.py; the active local Nano configuration is not replaced during comparisons. [NVIDIA Super model card](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/modelcard) identifies its Nemotron Open Model License and configurable thinking; [NVIDIA Ultra model card](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard) identifies OpenMDW 1.1 and configurable thinking. These metadata checks establish neither exact hosted protocol compatibility nor 6D quality. Shared public endpoints are used for this evaluation, with no deployment or dedicated GPU purchase.

## Inspect without inference

Open http://127.0.0.1:8768/, refresh, select Thermal or Guidance and control, then Investigate to read saved history and the new guidance. Connect AI contains the read-only comparison status. GET /api/model-evaluation/status and GET /api/model-evaluation/comparisons/{id} are read-only; only the explicit POST /api/model-evaluation/start action can start a comparison. The service holds credentials privately and returns no key. Comparison artifacts are saved in the existing local workspace database, outside user project revisions.
