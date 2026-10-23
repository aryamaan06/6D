# Current Assistant qualification and optional service connections

Open http://127.0.0.1:8768/ and select **AI quality & tools** in the left sidebar. This page supplements the existing requirement Inspector/Assistant; it does not replace the engineering workflow.

## Separate credentials

Each service has a different private form:

1. **Connect AI** at the top accepts **Nebius Token Factory only**. The existing optional Windows Remember setting is unchanged.
2. **AI quality & tools → Optional metrics in LangSmith** accepts the **LangSmith** key. Choose the account's US/EU region and, only if required, workspace UUID. This connection is memory-only.
3. **Source library → Optional Tavily connection** accepts the **Tavily** key and an absolute cumulative app search-credit ceiling. This connection is memory-only.

Connecting keys makes no provider request and does not validate account authentication. Entering different services' keys into Connect AI repeatedly replaces the Nebius connection. Keys are never requested in chat, returned by status, stored in browser storage, or included in evaluation exports.

## Qualification

**Run four live checks** prepares disposable constructed projects, then uses the currently selected Nemotron model and actual investigation engine. It exercises supplemental reference text, powered-flight scope, a decreasing thermal threshold with unchanged physics, and unsupported control evidence. Expected states/reference metrics are evaluator data, outside model prompts. Quoted instructions remain untrusted supplemental context.

The enforced batch ceiling is **USD0.80 / 24 request reservations** within the existing **USD29.50** cumulative ledger. Existing six-request/per-model case ceilings remain. The fixed pack currently fits Nano or selected Super; it rejects a selected model whose maximum case allocation exceeds this fixed batch ceiling rather than falling back. It never activates a model or changes the global CLI choice. A failed state or workflow contract stops the pack; remaining cases are untested. There is no automatic retry/resume.

Every receipt retains exact snapshots/source versions, canonical findings, reads/rechecks, accepted/rejected explanations, citation checks, provider settings, accepted-response token usage, observed latency and conservative reservations. Historical receipts remain unchanged after source changes. A same-adapter recheck establishes reproduction, not independent physics validity. An automated workflow pass does not establish semantic correctness. Independent human review remains pending.

Expand **Concrete next checks and missing evidence** to see application guidance captured with each receipt. Flight and attitude numerical gaps now receive domain-specific guidance. Numerical quantities remain application-owned; Nemotron commentary is qualitative.

## LangSmith

Preview is local and read-only. The exact preview includes only verified model ID, receipt/report/source hashes, fixed case IDs/states, bounded workflow flags, observed timing/counts and conservative reservation amounts. It excludes prompts, summaries, questions, engineering inputs/values, source text, arbitrary labels and credentials.

An explicit upload sends one completed chain run to the fixed regional LangSmith `/runs` endpoint. It records API acceptance separately from model quality and cannot change an investigation or calculation. Each qualification gets one retained attempt, including ambiguous failures; a local lifetime bound limits uploads to twenty. There is no automatic tracing, retry, project sharing or public post. LangSmith account charges are separate from Nebius dollar accounting.

Transport uses the [official REST tracing contract](https://docs.langchain.com/langsmith/trace-with-api), checked October 24: API-key authentication, optional workspace header, explicit run timestamps/project name, and fixed regional endpoints. The standard-library transport keeps this small, explicit one-shot upload outside inference and avoids background SDK retries.

## Tavily

The existing [source-connected Assistant](SOURCE_ASSISTANT.md) remains the research workflow: explicit Basic search, captured unverified results, review the source form, then separately save/link a reference. A search never alters numerical findings or proves source authenticity/applicability. The [Tavily search contract](https://docs.tavily.com/documentation/api-reference/endpoint/search) was rechecked October 24; request depth, usage reporting and no automatic answer/raw-content settings are preserved.

For connection or service failures, inspect the retained receipt before another deliberate attempt. HTTP401/403 guidance names the authentication issue; an HTTP429 asks for provider-limit review. No lost response is assumed to prove non-delivery.
