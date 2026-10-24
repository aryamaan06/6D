# Build E results — optional remembered connections

Delivered October 25, 2026, for the approved A–F backlog. Open **http://127.0.0.1:8768/** and refresh to build **a8807e9db185**. E is complete; F hosted access/isolation is still pending.

## Result

Tavily and LangSmith have independent, explicitly opted-in Windows-encrypted remembering. Restart restores the key and bounded service settings locally. **Forget saved key** preserves the current session; **Disconnect and forget** removes both. Session-only replacement removes an earlier saved copy so an old key cannot return on restart.

Tavily restores its absolute credit ceiling without resetting request reservations or its provider-usage review gate. LangSmith restores its region/workspace but still requires an exact preview and deliberate upload approval. Connect/restore/status make no provider calls and do not establish that a key is valid. Existing real optional-service keys were not silently saved or replaced.

## Verification

- The final scoped regression ran **96 distinct test methods: 95 passed, one skipped, zero failures/errors**. This includes 35 methods in the three new credential/service/HTTP modules and 61 existing affected regressions. These are scoped counts and overlap earlier project checkpoints; they are not a new full-suite count.
- Native Windows DPAPI tests passed for protected storage, service-specific entropy, cross-service substitution rejection, corrupt data, validated metadata, restart and pre-E Nebius compatibility. The skipped test needs Windows symlink-creation privileges; mocked linked/reparse-ancestor guards passed. Native Linux/macOS remembering is not claimed.
- HTTP checks cover legacy bodies, strict optional booleans/unknown fields, foreign-origin rejection, active-request conflicts, storage failure preserving the old connection, private-root isolation, exhausted/persisted Tavily accounting and credential-excluding stopped backups.
- Headless Chrome with the real HTTP server and synthetic keys passed **eight interaction groups**, including three backend starts, optional opt-in, EU/UUID restoration, service isolation, Forget, Disconnect, no resurrection and narrow viewport access. Only the four deliberate connection-control POSTs occurred. No search, upload, inference, external browser request or JavaScript error occurred. Earlier harness attempts had loading/selector/endpoint mistakes; the final result is the successful integrated run, not a claim that those attempts passed.
- The actual application restarted successfully and was read-only checked at the address/build above. The existing remembered Nebius connection restored. New optional Remember checkboxes were unchecked. No POST, external browser request or JavaScript error occurred during delivery inspection.
- Before/after comparisons matched **22 database tables / 80 rows** and **three private configuration/credential files**. Existing projects, revisions, historical receipts, provider settings, reservations and ciphertext were unchanged. No user project was recalculated.
- Runtime Python sources follow canonical LF bytes. Documentation/publication checks exclude private credentials, databases, raw logs and local test artifacts.

Machine-readable evidence: [Build E checks](validation/BUILD_E_CHECKS.json). The private detailed logs and browser screenshots remain under ignored `work/build-e/`; the public summary contains no keys or project inputs.

## Reproduce the new checks

Run from the repository root using Python 3.10+:

```console
python -m unittest discover -s tests -p test_service_credentials.py -v
python -m unittest discover -s tests -p test_optional_service_connections.py -v
python -m unittest discover -s tests -p test_optional_connection_api.py -v
python tools/check_source_consistency.py
```

The native DPAPI branches require Windows. Other platforms exercise controlled unsupported-platform behavior and session-only use. HTTP tests open local loopback sockets and use synthetic keys/offline transports; they do not require provider accounts. Exact regression module names/counts are in the JSON summary.

## Boundaries

No paid Nebius inference, Tavily search or LangSmith upload was made by E. No model was selected/promoted and no allowance increased. Current-source live AI qualification and independent human/user review remain pending; historical live records retain their original dates/source identities. Encrypted local storage does not provide public hosting or team security. [One-time opt-in instructions](REMEMBERED_SERVICE_CONNECTIONS.md) · [Acceptance](BUILD_E_ACCEPTANCE.md) · [Remaining F scope](HACKATHON_BUILD_SCOPE.md).
