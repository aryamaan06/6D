# Engineering-workflow Assistant evaluation

**Completed live result:** see [LIVE_WORKFLOW_RESULTS.md](LIVE_WORKFLOW_RESULTS.md). Twenty tasks completed, one stopped and nine were untested. Super is retained; original scores are not retroactively revised by the new offline comparison guard. Independent human review remains pending.

This evaluation uses the actual bounded Assistant on ten constructed scenarios, with the same evidence, questions, protocol and output limits for Nano, Super and Ultra. It is separate from the original six-case comparison that justified selecting Super. None of these scenarios is independent customer evidence or a blinded held-out test.

| Case | Expected engineering interpretation |
| --- | --- |
| Orbital criterion met | Conditional sampled criterion with declared grid agreement; no true-error or mission guarantee. |
| Missing orbital accuracy | Completed diagnostic trajectory; requirement unresolved. |
| Tight orbital tolerance | Grid disagreement exceeds supplied tolerance; requirement unresolved. |
| Near-limit criterion | Declared allowance overlaps the limit; no pass. |
| Changed thermal limit | The criterion changed while the calculated temperature remained unchanged. |
| Changed linked density | Follow the declared drag-to-beam dependency; do not invent simultaneous physics. |
| Blocked upstream orbit | Missing source accuracy blocks the downstream scalar calculation; no fabricated drag result. |
| Power-capacity shortfall | Output-power adequacy and usable-energy adequacy are separate. |
| Single-axis pointing | Bounded sampled response under its declared assumptions. |
| Unsupported control | Missing model/evidence is not a finding of physical impossibility. |

The three candidates create thirty planned tasks. A failed task stops that candidate; remaining tasks are labelled untested. A batch stop preserves partial evidence. There are no automatic retries, fixture fallback, resumed live runs or model-selection changes.

## Limits and accounting

The batch ceiling is **USD 3.00** and 180 request reservations, within the existing approved cumulative USD 29.50 ledger. Each task retains the existing six-request limit and candidate ceilings (Nano USD .10, Super .20, Ultra .35). The earlier USD 1.50 ceiling did not fit the offline capacity forecast; no request was sent under that proposed limit.

The offline forecast is a synthetic capacity check, not observed model performance or billed cost. Reservations retain full permitted output capacity and conservative input estimates. Actual accepted-response token usage and elapsed time are recorded separately; rejected/failed requests can have incomplete usage coverage. The provider bill and account balance are not inferred from the local ledger.

Current configured model IDs and price ceilings remain those already reviewed for this account. The [provider's Ultra cookbook](https://raw.githubusercontent.com/nebius/token-factory-cookbook/main/models/nemotron/nemotron3-ultra-550b-a55b.md) was checked October 20 and lists USD 1/M input and 3/M output. [Nano](https://raw.githubusercontent.com/nebius/token-factory-cookbook/main/models/nemotron/nemotron3-nano-30b.md) and [Super](https://raw.githubusercontent.com/nebius/token-factory-cookbook/main/models/nemotron/nemotron3-super-120B.md) documentation confirms the family and tool-calling interfaces but does not state their prices. Their configured .06/.24 and .30/.90 rates remain backed by the founder's October 15 console evidence and October 16 pricing check; the local counter is not a provider invoice. Provider cookbook examples differ in regional endpoint/casing details; the account-validated global endpoint and routing IDs are preserved.

Common settings are the established forced-action protocol, native no-thinking profile and 2048 output-token ceiling. The comparison measures this application workflow under those settings, not every model's maximum reasoning capability.

## Read the results

Open **Connect AI** in the existing workspace and find **Engineering workflow evaluation**. Refreshing its status makes no inference request. The scorecard shows completion, workflow checks, conservative reservations and elapsed time. Its download contains the full recorded responses, citations, rejected interpretations, plan/evidence digests, usage and per-case stop reasons.

Workflow checks test required reads, exact evidence identifiers, reproducibility, revision interpretation and preservation of canonical findings. Limited wording/numeric checks can miss errors or reject acceptable language. They do not establish semantic correctness. Independent human engineering review remains pending even if every workflow check passes. Any review authored by Codex must be labelled as AI review, not an independent human judgment.

## Historical proof and current evidence

An older, internally consistent comparison remains evidence for its recorded case pack even when application source files change. The selection gate now validates that historical proof without claiming it is a fresh evaluation of the expanded workflow. Live investigations still require current verifier fingerprints, and changed source files still stop work before another request. No saved comparison, manual judgment, project result or model-selection file is rewritten by this correction.

The private key stays only in server memory. No key is returned by these endpoints, saved in evaluation files or requested in chat. A disconnected server cannot start the paid batch. The host starts the already-authorized batch only after private connection and offline acceptance.

Read-only endpoints: `/api/workflow-evaluation/status` and `/api/workflow-evaluation/runs/{id}`. The explicit host action is `POST /api/workflow-evaluation/start` with the exact approved batch ceiling. Original six-case comparison endpoints and proof records remain separate.
