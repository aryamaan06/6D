# Owner-approved remaining capacity — October 26

Refresh **http://127.0.0.1:8768/** for build **b2b49af04e8b**. The owner approved using the remaining balances shown in the supplied screenshots, through explicit application actions. No paid request was made to apply or verify the change.

## Applied local limits

| Service | Previous reservations retained | New cumulative app ceiling | Available for future reservations immediately after migration |
| --- | --- | --- | --- |
| Nemotron through Nebius | USD4.80367468 | USD63.05367468 | **USD58.25** |
| Tavily | 1 basic credit | 4,125 basic credits | **4,124 credits** |

Cumulative ceilings include the already recorded reservations; they do not authorize that cumulative amount as additional usage. Accounting was not reset. The screenshot's Tavily usage was one credit out of a total of 4,125, giving 4,124 available. Provider balances are not automatically synchronized; later explicit requests reduce the retained app capacity. No top-up or additional card spending is authorized.

The earlier fixed owner ceilings are updated only to these exact cumulative bounds, not a generic larger ceiling. Per-investigation/request/batch limits, no-retry behavior, all three model choices, default Super and explicit search/inference starts remain unchanged. Hosted/public reservation limits remain separate and **unchanged**; this local update is not a hosted deployment or authorization to raise public visitor budgets.

The existing inference allowance operator tool records an audited increase with the same approval identity and reservations. Its new guard also checks that future capacity does not exceed USD58.25. The offline Tavily operator tool updates settings in the existing encrypted credential envelope, verifies the same key on restoration, preserves all search receipts and permits at most 4,124 future credits. Both tools require the local server to be stopped; neither contacts a provider. New local receipts remain ignored under `work/balance-limits/`.

## Clear blocked-search behavior

The rocket now explains why Tavily Search is unavailable: exhausted app allowance, missing connection, draft/historical context, usage review, a pending operation or missing target/query. It does not expose financial figures in the normal conversation. **Enter adds a line to the query; click Search references to send it.** Search still requires that deliberate action and never automatically repeats.

## Verification

- **67 affected offline Python methods: 66 passed, one platform-related skip.** Coverage includes audited allowance migration, exact future-capacity boundaries, protected credential settings/restoration, retained search reservations, owner AI and hosted runtime regressions. No full-suite run is claimed.
- **13 rocket browser groups passed**, with synthetic transports and zero external calls. The new exhausted-capacity case checks a visible reason, a disabled search, restored controls after status refresh, retained query and zero premature search requests. Existing question/model/context, reference-copy, mobile and hosted-owner boundaries also passed.
- **26 preservation checks matched.** Existing workspace records, historical approval rows, reservations, nonbudget provider configuration, model default and other encrypted credentials are unchanged. Only the authorized inference cap/audit row, local configuration cap and encrypted Tavily allowance settings changed. The same Tavily key was verified after the protected update.
- Actual startup restored Nebius, Tavily and LangSmith. Read-only status reports Nemotron configured with USD58.25 available and Tavily connected/search-enabled with 4,124 credits available. Runtime LF consistency passed over 64 Python files.

Budget/credential source fingerprints changed, so earlier model qualification records remain historical evidence under their captured versions. No new semantic or live-provider qualification is implied by these offline limits checks. Numerical solvers and saved engineering findings are unchanged.

Reproduce scoped checks with `PYTHONPATH=src;tests` on Windows (`src:tests` on POSIX):

```console
python -m unittest test_allowance_migration test_balance_allowances test_service_credentials test_workspace_research test_workspace_ai test_hosted_runtime -q
node tools/check_rocket_browser.mjs
python tools/check_source_consistency.py --git-ref HEAD
```

[Sanitized machine-readable checks](validation/BALANCE_LIMITS_CHECKS.json)
