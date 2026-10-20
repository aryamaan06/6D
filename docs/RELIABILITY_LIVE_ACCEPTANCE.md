# Reliability build and reviewed Super selection

October 16, 2026, Asia/Calcutta. Same local application at http://127.0.0.1:8768/, final build **43a76efc537e**. Final regression: 405 tests passed, followed by all eight focused model-selection checks. See INVESTIGATION_RELIABILITY.md for implemented controls and offline validation.

## Live result under policy v2

Comparison: `5f1c35cfd6b245168496c4dce1ce9828`. One explicitly approved batch, no profile sweep, retries or fixture fallback. Candidate evidence, questions, tools, thinking profile and output ceiling were identical. Per-case reservation ceilings were Nano USD 0.10, Super USD 0.20 and Ultra USD 0.35, within a USD 1.50/90-reservation batch ceiling and the audited cumulative USD 29.50 allowance.

| Model | Attempted | Completed / workflow passes | Skipped after stop | Reserved USD |
| --- | ---: | ---: | ---: | ---: |
| Nano | 6 | 6 / 6 | 0 | 0.03344364 |
| Super | 6 | 6 / 6 | 0 | 0.15244380 |
| Ultra | 3 | 2 / 2 | 3 | 0.22067900 |

There were **59 actual request reservations and 59 accepted live action responses**. The Ultra final action was structurally accepted, but its proposed explanation was rejected by the wording gate; accepting an action response is not accepting its explanation. The batch reserved **USD 0.40656644**. The prior USD 0.30432376 remains retained: cumulative reservations are **USD 0.71089020** of USD 29.50, with **USD 28.78910980** reservation capacity remaining. These numbers are conservative application accounting, not billed cost or current Nebius wallet balance. Project/revision/calculation-table digests were unchanged before and after.

## Review and corrected filter limitation

Nano and Super preserved the canonical outcomes and exact evidence citations across all six tested cases. Both distinguished the limit-only revision from changed calculated temperature. Super gave more direct engineering follow-up: check heat-load/emissivity/applicability, obtain a supported control analysis, resolve units with source verification before rerunning, and obtain atmospheric/coefficient/reference-area evidence. Nano's control/invalid-unit responses lacked concrete next actions; its invalid-unit response also used ambiguous cannot-satisfy wording. This is a wording/usefulness difference, not a different physics calculation.

Ultra produced detailed, supported thermal explanations and then a correct control evidence-gap explanation. The initial wording check falsely rejected its explicit statement that this was **not a finding that the design was physically impossible**. Manual inspection identified the false positive. The check now handles that explicit negation and narrowly attributed exact source quotes. The recorded canonical reason was quoted rather than asserted as a new result. Offline replay of the captured text now accepts it; **the original live receipt, failed state and scores remain unchanged**, and the remaining three Ultra cases remain untested. No paid rerun was made to improve its table results. This does not establish poor Ultra reasoning or a complete Ultra quality pass.

The earlier v1 comparison remains separate and unchanged. Its strict first-revision history-read rule and insufficient Ultra case ceiling are not retroactively rescored under v2. Neither comparison is a broad or statistical model ranking, independent specialist review, or whole-spacecraft validation. The limited explanation checks can still miss mistakes and produce false positives.

## Model decision

**Super is selected as the default for the implemented saved-requirement Assistant.** It completed all six current live workflow cases and its manually reviewed concrete next actions justify the higher cost for this bounded use. Observed Super reservations were about 4.6 times Nano's for these six cases; the decision favors useful explanations within the approved development allowance, not lowest cost.

The decision is recorded under `model_reviews.super` as sixd.model-manual-review.v2, bound to the exact report/plan and paired Nano receipt digests. `candidate_selection_gate` returned eligible after recomputing the workflow/evidence checks and inspecting the explicit review. This is a deliberate host selection; the gate never changes routing itself.

The app-only `.local/project-assistant-model.json` references the comparison and candidate. Each config resolution verifies the saved wrapper, original report, current case pack and manual review. Missing, malformed, tampered or nonqualifying proof blocks live setup without a silent fallback. The Super job has a six-request/USD 0.20 reservation ceiling. No model selector or automatic escalation/router was added.

**The global Token Factory configuration remains Nano**, preserving the separate orbital CLI baseline. App selection replaces only the project Assistant's model and verified price ceilings, sharing the same memory-only connection, cumulative ledger and workflow. The approval ID retains its historical usd5 wording; the audited ledger ceiling is USD 29.50 with no usage reset.

## Evidence and opening

The comparison/settings screen links to its saved JSON, including the appended manual review and decision outside the unchanged original report. Ignored local artifacts under `artifacts/model-comparison/` use the comparison ID above with `.json`, `-before.json`, `-acceptance.json`, `-super-review.json`, `-decision.json` and `-ultra-reassessment.json` suffixes. Consistency digests are unsigned local records, not authenticated third-party approval.

The final backend restart clears the private key. Local calculations and saved evidence still work. Connect the key privately when choosing to start the next live investigation; no repeated acceptance batch or terminal commands are required.

## OpenAI candidate and next feature

The proposed OpenAI candidate remains **GPT-6.1 Sol, high reasoning via Responses**. It has not been integrated or evaluated here, and no OpenAI API call was made. The [official model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol) documents the model; [GPT-6 guidance](https://developers.openai.com/api/docs/guides/latest-model) specifies Responses for function calling. The next visible product expansion is plots comparing actual engineering results, limits and revisions, subject to a new explicit build instruction. “What is next?” requests a plan, not execution.

Final read-only production browser acceptance passed: actual selected Super and its USD 0.20 job cap, USD 29.50 development ceiling, preserved recorded Nano history, v2 model decision and unchanged reservations. No POST requests, inference or JavaScript errors. Receipt: work/reliability-super-delivery-browser.json.
