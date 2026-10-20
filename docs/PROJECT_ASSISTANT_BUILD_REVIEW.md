# Project Assistant integration — October 16, 2026

Delivered locally at http://127.0.0.1:8768/, build `d8b54d15e067`. This receipt covers the implemented and offline-tested project investigation workflow. At that delivery, live acceptance was pending private connection. The subsequent October 16 two-case project live orchestration gate passed as recorded below and in PROJECT_ASSISTANT_LIVE_ACCEPTANCE.md. The October 14 orbital investigations remain separate preserved evidence.

## Working implementation

An explicit Investigate action opens the Assistant for the selected requirement and saved revision. A question and scoped evidence go through the existing Nano Token Factory transport, using a separate bounded project-action adapter. The model may read the requirement, read its model/evidence, inspect scoped revision differences, request a fresh calculation and finish with actual evidence citations. Required reads and applicable rechecks precede completion. It cannot edit inputs, substitute thresholds, invoke arbitrary programs or change the canonical finding.

Rechecks establish reproducibility of the maintained calculation, not independent physical validation. A source change or a mismatch stops the investigation. Unsupported models remain unassessed and are not given an invented solver. AI prose is visibly interpretation, separate from the saved requirement finding.

The server records queued/running/completed/failed jobs, actual accepted actions, partial evidence, selected revision/review digest, model/settings, citations and conservative request reservations in the existing workspace database. Refresh reads saved history. Restart interrupts unfinished jobs without automatic retry; prior partial evidence and reservations are retained. Old workers cannot overwrite recovered jobs. Changed model/settings cannot inherit another configuration's live-validation status.

Connect AI uses a password field. Credentials remain only in local server memory and are never returned by status or stored in project/job records or browser storage. Connecting, navigating and refreshing make no inference calls. Explicit Start sends the question and scoped project records to Nebius. The same cumulative USD 5 approval/ledger is used, with at most six requests and USD 0.10 in conservative reservations per job. Failed requests retain their reservations. Disconnect stops further reservations; an already reserved in-flight request can still finish.

## Verified

- **324 tests passed**, including the existing orbital/provider suite and new engine, wire-protocol, job, budget/privacy and HTTP tests.
- Real TokenFactoryProvider request construction and response decoding were exercised through injected offline transports, clearly labelled `offline_transport_fixture`; no paid provider was called.
- Browser walkthrough: missing-key blocking; private connection without inference; live-job polling against the offline provider; actual accepted actions; cited requirement/model/recheck records; canonical finding separate from interpretation; JSON download; original history after reload; question/context reset when switching requirements; unsupported GNC abstention; disconnect; mobile layout; no JavaScript/CSP errors.
- A changed thermal revision was calculated, investigated and shown as an unmet criterion; selecting the original revision restored its original met finding and investigation history.
- The actual 8768 service was independently checked for runtime/build identity, preserved project records, the Assistant and password dialog, correct Nano routing ID and absence of browser errors. No key was connected during that check.
- Original cumulative reservations remained USD 0.03079626 when the delivered service was checked; no new paid request was made. Reservations are not an invoice or current account balance.

## Subsequent live acceptance — October 16

Arya connected the key privately in 6D. The thermal investigation completed four actual Nano native tool responses, read its locked requirement/model and produced a fresh same-adapter result exactly matching both the saved evidence and a separate local rerun. The unsupported GNC investigation completed three responses, retained its canonical not-assessed finding and produced no solver, metric or recheck. Both project/run snapshots remained unchanged. All seven events recorded native_tool_call, provider-origin call metadata and finish_reason=stop; citations exactly matched the recorded evidence. The seven requests reserved USD 0.00780588 conservatively under the existing cumulative USD 5 allowance. No further paid acceptance run is needed.

Live orchestration passed; explanation quality still needs evaluation. In the GNC summary, the opening correctly says not assessed and identifies the missing adapter, but the later wording cannot be satisfied should read cannot be established as satisfied. The canonical finding remains not assessed, not a demonstrated vehicle defect. This limitation is preserved rather than silently editing the model receipt. See PROJECT_ASSISTANT_LIVE_ACCEPTANCE.md for exact IDs, provenance and verification. The preceding Verified bullets describe the original offline build checks, not this later paid acceptance.

The broader model comparison/routing, new engineering disciplines and simulation/playback remain in the full 6D plan. This integration does not complete the entire startup platform or establish model answer quality across arbitrary engineering questions.

## Primary sources checked October 16

- [Nebius function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling): named function selection and backend dispatch.
- [NVIDIA model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) and [Nemotron model license](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/): model identity and governing terms; no weights are bundled.
- [Nebius Nemotron catalogue](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference): displayed Nano rates USD 0.06/M input and USD 0.24/M output, matching the existing configured ceilings. Account availability and successful inference still require an actual live response.
