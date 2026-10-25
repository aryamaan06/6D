# Build F — protected hosting preparation

Prepared October 25, 2026. **The protected server and deployment package are implemented and tested locally. Public hosting is not complete:** no cloud instance, domain, TLS certificate or paid resource was provisioned. Nebius AI Cloud billing was not configured; provider choice, actual cost and an operational ceiling still need review before deployment.

The owner application remains at **http://127.0.0.1:8768/**, build **0f85bf3c7477**. A separate loopback-only hosted-mode preview is running at **http://127.0.0.1:8770/** on the development machine. Its generated invitation is in ignored `work/hosted-preview/invitation.txt`; it is not an API key or a public deployment credential. The preview's state is separate from `.local` and inference is disabled. It is a development artifact, not the portable deployment launcher.

## Implemented behavior

- A separate gateway requires a private invitation and an exact configured origin. Persistent unpredictable session cookies are HttpOnly/SameSite Strict, with Secure and the `__Host-` prefix under HTTPS. The database retains token hashes, not raw cookies. The shared invitation is bounded demo access, not a production account or authenticated engineering approval.
- Each browser session receives its own persistent database/private runtime and a calculated constructed rocket reference. It receives no owner projects, history, credentials or provider configuration. Existing results are preserved across restart without automatic recalculation.
- Visitors can use the allowed engineering workflow, stage revisions, run checks and export their own records. Knowing another visitor's project ID does not grant access. Key management, shutdown, qualification/diagnostics, Tavily searches and LangSmith uploads are blocked server-side and their unavailable controls are hidden in hosted views.
- Default limits bound lifetime visitor allocation (20), session lifetime (24 hours), reads (600/minute/session), writes (12/minute/session), login attempts (10/minute globally), active connections (32), socket wait (15 seconds) and workspace storage admission (200 MiB/session). Limits are bounded operator configuration. These are admission controls, not guarantees against denial of service or exact disk/CPU upper bounds for already admitted calculations.
- Sign-out revokes access without deleting records/reservations, remains possible at the storage ceiling and refuses an active AI job. Mutations waiting on the per-session write lock recheck expiry/revocation before execution; a stale authenticated request cannot write or start inference after sign-out.
- Live AI is off by default. Optional server-only configuration requires a reviewed provider file, separately mounted key, frozen prior cumulative ledger and explicit handoff confirmation. Total/day/session reservations are atomic and persistent, in addition to existing per-investigation controls. Prior development reservations consume the total; failed requests, new sessions and restarts do not refund it. The old independently writable ledger must stop authorizing paid calls at cutover; disconnected ledger copies cannot enforce one shared allowance.
- Authoritative hosted spending is displayed separately from provider billing. Keys never enter visitor forms, browser storage, status bodies, the image or the public source. The Docker/Caddy recipe has a private application port, HTTPS proxy, persistent volume and non-root/read-only application filesystem. Cloud platform/TLS/operations still require actual deployment validation.

## Recorded verification

- **106 distinct affected test methods** across the new hosted modules and existing local APIs: 105 passed and one native Docker/Compose check skipped because Docker is not installed on this Windows machine. This combines an 88-method regression with final affected checks, counting overlapping methods once. The final 58-method run passed with no failures/errors/skips after the UTF-8/source-byte correction. This is not a complete project-suite count.
- Native HTTP tests cover exact Host/Origin, duplicate headers, strict bodies, forged/expired/revoked cookies, private cookie flags, restart/session allocation, isolated reads/writes, route restrictions, thread/rate/storage admission, controlled errors, active-job sign-out and deterministic queued-write revocation/expiry races.
- Budget tests cover concurrent visitors, exact policy/approval matching, frozen carryforward, UTC rollover/backward clocks, persistent counters, invalid/corrupt accounting and retained reservations after downstream rejection. No transport/provider was contacted.
- **Nine integrated Chrome groups** passed against the actual hosted HTTP server: invitation, populated example, two visitor isolation, real thrust edit/save/recalculation, session-scoped export, unavailable controls across dynamic views, backend restart, narrow viewport/cookie handling and sign-out. The second visitor's baseline stayed unchanged. Zero JavaScript errors, external browser requests or provider-action requests occurred. Seven additional mocked interface groups test specific login, expiry and budget-display states; they are not live-provider evidence.
- The owner application was reopened and read-only checked at its normal address. Its remembered Nebius key restored. Before/after hashes matched **22 tables / 80 rows** and **three private configuration/credential files**. No owner project was rerun and no allowance/configuration/key changed.
- Source-byte checks passed for **62 runtime Python files**, with canonical LF preserved. The visual check caught an encoding problem in the shared HTML; the final changes were reapplied from exact UTF-8 originals and the real browser workflow rechecked.
- The pinned-action [Linux/container CI run](https://github.com/aryamaan06/6D/actions/runs/40161774801) **passed** for source commit `a30d2e4a5224ac8a82d4ce29b42250cabac9271e`: Linux scoped hosting checks, image build and a constrained container login/restart/sign-out smoke test all completed successfully. This provides actual Linux/image execution evidence beyond the Windows checks. The public summary records job/step outcomes rather than inventing an additional CI test count. Real public DNS/HTTPS and cloud operations remain separate deployment checks.

[Machine-readable checks](validation/BUILD_F_CHECKS.json) · [Acceptance](BUILD_F_ACCEPTANCE.md) · [Operator deployment guide](HOSTED_DEPLOYMENT.md). Detailed local logs/screenshots and the preview invitation remain ignored under `work/`.

## Reproduce

```console
python -m unittest discover -s tests -p "test_hosted*.py" -v
python tools/check_source_consistency.py
```

These checks use synthetic secrets and offline transports. Native Compose parsing skips without Docker. The checked-in workflow adds real Linux/container execution when run; it uses synthetic invitation data only and never provisions a cloud host or contacts a model provider.

No paid inference, Tavily search, LangSmith upload or cloud spending occurred in this preparation. Current-build live AI qualification, owner-led interface refinement/walkthrough, external human/user evidence and submission packaging remain separately pending. F remains open until an approved host is deployed and the real URL, TLS, persistence, cost controls and allowed live AI behavior are verified.
