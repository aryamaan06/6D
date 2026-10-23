# Optional Tavily reference-search contract

October 24 live result: the connected service completed one Basic search returning five NASA references, using one reserved and provider-reported credit. Exact preview/form handoff and preservation checks passed; see [TAVILY_LIVE_RESULTS.md](TAVILY_LIVE_RESULTS.md). Results remain unverified supplemental material.

`WorkspaceResearch(store, sources, transport=None)` supports explicit searches for references relevant to one saved engineering target. It shares the source library's project/revision validation. It never creates a source, link, calculation, AI investigation or engineering verdict.

## Connection and credit accounting

`status()` returns `sixd.research-status.v1`, provider, private-key presence, the connected absolute credit allowance, persistent reserved credits, remaining local capacity, active requests and limitations. The key value is never returned. A key is stored only in server memory; no environment key is automatically imported. `connect(api_key, credit_limit)` and `disconnect()` perform no provider request.

The chosen `credit_limit` is an absolute local cumulative allowance from one through twenty, not an additional grant on each connection. Existing reservations survive reconnects and server restarts. After restart, the key and chosen limit must be supplied again; the saved count remains. A request reserves one credit before transport. Failure or interruption retains it; there are no automatic retries or fixture fallbacks. Interrupted requests remain visibly pending. A lower newly selected ceiling cannot discard existing reservations.

The local reservation count is not a provider balance or billing statement. The application cannot detect an expired promotional balance or disable account-level pay-as-you-go. Explicit searches consume the configured Tavily account's credits under its provider settings. Service basic-search pricing was checked in the [official credits documentation](https://docs.tavily.com/documentation/api-credits); the fixed request is based on the [official search API](https://docs.tavily.com/documentation/api-reference/endpoint/search). These references describe the service contract, not an actual live verification result for 6D.

If reported provider usage exceeds the local one-credit request reservation, the original receipt retains that usage and an explicit warning. Further searches are blocked for review. `usage_review_required` is derived from immutable saved receipts, so reconnecting, raising the chosen allowance or restarting cannot clear it. `can_search` becomes false in status and project research views. The past reservation is not retroactively rewritten or represented as billed usage.

## Saved-scope operations

- `list(project_id, revision)` returns `sixd.project-research.v1`: exact selected project/revision, `can_search` for the latest revision, `library_digest`, current explicit targets, at most one hundred saved search summaries, limitations and a digest.
- `get(search_id, project_id, revision)` returns the original request's latest retained version only within that project and at/before the selected revision. Historical records remain unchanged; later context is not substituted into them.
- `search(project_id, revision, target_id, query, expected_digest)` requires a connected key, the latest saved revision, an available explicit source-library target and the exact displayed library digest. It captures the original target, context/project/library digests, run identity and query before reserving and sending.
- `preview_source(receipt, result_index)` is a pure helper returning `{source_id:null, base_version:null, title, url, excerpt, details}` for the existing manual source form. Details preserve the original project, revision, target, query, request identity, retrieval time, receipt digest and truncation disclosure. Filling a form is not a save; source creation and linking remain explicit, separate operations.

Every search has append-only `project_research_versions` records. Version one is the request reservation (`pending`); version two is its controlled `completed` or `failed` receipt. They share immutable request/scope fields. Reads verify digests and identity consistency. No founder/demo search is inserted during startup or navigation.

## Transport and output

Only the entered query and fixed parameters are sent: `search_depth=basic`, `topic=general`, `max_results=5`, answers/raw content/images disabled, automatic parameters disabled and usage requested. The application does not send the target, project name, numerical evidence, source library or configuration automatically. Users must review their own query before sending it.

The standard-library transport sends one POST to the fixed HTTPS Tavily endpoint with private Bearer authentication. It disables environment proxies, refuses redirects, times out after thirty seconds and bounds the response to one MiB. Duplicate JSON fields, nonfinite values and malformed responses are rejected. Credentials echoed by the provider are rejected rather than persisted, including JSON-escaped quotes/backslashes and decoded nested object keys or values. Raw provider exceptions and error bodies are not returned.

Accepted results contain index, title, HTTP(S) URL, excerpt, optional relevance score and a truncation flag. At most five results are retained. Excerpts are bounded to eight thousand characters and titles to two hundred. Unsafe schemes, credentials in URLs, local/private IP addresses and obvious nonpublic hostnames are rejected. No URL is fetched by 6D, and public-looking hostnames are not a DNS-authentication claim.

Receipts use `sixd.research-search.v1`, including `search_id`, version, project/revision, creation/completion timestamps, state, original query/target/context identities, fixed request parameters, reserved credits, provider request identity/reported usage, results, controlled error or null, limitations and digest. Provider failures return a failed receipt with `{code,message,next_step}`; preflight errors raise the existing workspace error/conflict types before transport or reservation.

Search relevance is not engineering confidence. Retrieved text remains unverified supplemental information, and it cannot change a numerical finding or establish model applicability. Tests use injected synthetic transports; live Tavily qualification is a separate step.
