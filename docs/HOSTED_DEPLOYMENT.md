# Protected 6D review deployment

Build F preparation, October 25, 2026. **No cloud deployment, paid resource or public URL is established by this guide.** The existing owner workspace remains at http://127.0.0.1:8768/. Native Linux/container qualification and a real HTTPS deployment must be recorded separately from local preparation.

## Arrangement

```text
Invited reviewer → HTTPS / Caddy → 6D hosted application → isolated persistent workspace
                                         │
                                         └─ Nemotron / Token Factory only if explicitly enabled
```

The hosted entry point is separate from the local owner server. A shared invitation code grants access to a bounded demonstration; it is not an individual identity or a production team account. Each browser session receives a separate persistent workspace with a constructed rocket example, rather than a copy of the founder's data. Authenticated reviewers can use the allowed engineering workflow in that session. Provider-key settings, server shutdown, batch qualification/diagnostics, Tavily searches and LangSmith uploads are unavailable to visitors.

A browser sign-out revokes its session. Session expiry bounds access; it is not a guarantee of automatic data erasure. The invitation code and server state are operator responsibilities. Use constructed or public data for this demonstration. Do not treat this preparation as authorization to host confidential spacecraft designs.

## Operator configuration

The hosted launcher is `tools/serve_hosted.py`. Its deployment configuration is explicit:

| Setting | Purpose |
| --- | --- |
| `SIXD_PUBLIC_ORIGIN` | Exact external HTTPS origin, including a nonstandard port if applicable. |
| `SIXD_STATE_ROOT` | Private persistent hosted state directory, separate from the source tree and owner `.local` data. |
| `SIXD_HOST`, `SIXD_PORT` | Internal listening address/port. The Compose recipe uses `0.0.0.0:8080` inside the application container only. |
| `SIXD_JUDGE_ACCESS_CODE_FILE` | Read-only secret file containing the invitation code, at least 32 characters. Never an API key. |
| `SIXD_LIVE_AI_ENABLED` | Default off. The supplied Compose recipe fixes it to `0`. |

The operator must choose access credentials and protect their files. Do not put secrets into Git, images, command-line arguments, browser forms intended for another service, or the public deployment env file. A secret-file path is configuration; its contents remain private.

Live inference, if subsequently approved, additionally requires `SIXD_PROVIDER_CONFIG_FILE`, `SIXD_NEBIUS_API_KEY_FILE`, `SIXD_INFERENCE_DAILY_CAP_USD`, `SIXD_INFERENCE_SESSION_CAP_USD`, `SIXD_PRIOR_BUDGET_FILE` and the explicit operator confirmation `SIXD_CUMULATIVE_LEDGER_HANDOFF_CONFIRMED=1`. Provider configuration contains the approved cumulative cap, model/endpoint/protocol, verified ceilings and approval identity. Before handoff, stop the local AI process and every other writer of the old ledger. Carry forward the frozen, verified prior reservations using the same approval identity and cumulative cap; do not create a fresh allowance or run two independent spending ledgers against the same approval. Never assume the development ledger or Token Factory balance authorizes a new public allowance. Persistent host-wide cumulative, UTC-day and session reservations remain conservative and are retained on failed requests. A storage or approval mismatch blocks requests rather than resetting usage. The existing per-investigation request/reservation controls also apply.

The Windows DPAPI files introduced by Build E are local user/device credentials. They are not copied to Linux or used as hosted secrets. This recipe does not enable Tavily or LangSmith visitor operations.

## Deployment recipe — after cost and access approval

The proposed target is a small CPU server, not a dedicated model-serving GPU. Token Factory continues serving the model. Provider selection and actual VM/disk/network prices remain subject to review; Token Factory promotional credits must not be assumed to pay for a VM.

1. Verify the chosen host's cost, persistent disk, region, firewall and access credentials. Agree an operational budget and judge-access/retention period before creating resources.
2. Point an approved hostname at that host and install a supported Docker/Compose runtime. Actual provider/firewall/TLS behavior requires deployment testing.
3. Place the generated invitation code in a private directory **outside** the repository. Make its file readable by the application container's UID 10001, without granting broad public access. Do not reuse an API key or account password.
4. Copy `deployment/hosted.env.example` to a private operator-controlled location outside the repository. Set `SIXD_DOMAIN`, `SIXD_TLS_EMAIL` and the absolute `SIXD_SECRET_DIRECTORY`; no secret values belong in this env file.
5. Review the recipe, base image versions and the build context before running:

   ```console
   docker compose --env-file /private/path/hosted.env -f deployment/compose.yaml config
   docker compose --env-file /private/path/hosted.env -f deployment/compose.yaml build
   docker compose --env-file /private/path/hosted.env -f deployment/compose.yaml up -d
   ```

   These are deployment instructions, not commands executed or approved by this preparation. The example hostname cannot receive a usable certificate as-is.

6. Check application/container health, HTTPS certificate, invitation login, two independent browser sessions, isolated project data, restart persistence and blocked administrative routes. Confirm no public mapping exposes application port 8080. Check the rendered review and exported reports against one another.
7. Record the actual URL, image/commit identity, host region, observed costs, checks and remaining limitations. Keep live AI disabled until its server configuration, allowance and deliberate live checks are separately approved.

The Compose recipe publishes only Caddy's ports 80/443. Caddy forwards to the application over the private container network and supplies HTTPS externally. The application runs as UID/GID 10001, has a read-only code filesystem, a bounded `/tmp`, reduced capabilities and a persistent named state volume. These settings reduce accidental exposure; they are not a complete infrastructure security audit.

## Persistence, updates and recovery

The `state` volume contains hosted session metadata, separate workspaces, receipts and reservation ledgers. Retain it across image updates. `docker compose down -v` removes named volumes and must not be used for ordinary updates. Losing a ledger does not authorize a fresh spending allowance.

Before backing up state, stop application writes and wait for active investigations. Protect the backup like application data; hosted state is distinct from the local owner's allowlisted backup tool. Secret files are backed up separately under the operator's private secret policy, never inside public release artifacts. Test restoration into a separate private environment with inference disabled before relying on it.

Update the image from a verified commit, preserve the state/ledgers, start it and rerun the delivery checks. Existing source-tagged engineering or AI receipts may become historical after code changes; do not rewrite their hashes or silently rerun them as part of deployment.

Invitation rotation, session expiry, retention and incident recovery must be tested on the deployed instance. Rotating the shared invitation alone must not be represented as proof that every existing browser cookie has been revoked. Do not erase reservation ledgers to revoke access or reset the example.

## Current limits

This is one bounded hosted demonstration instance. It does not provide production organization accounts, SSO, role administration, contractual data isolation, regional compliance assurances, broad abuse resistance or mission certification. Native Linux and constrained container execution passed in [the recorded CI run](https://github.com/aryamaan06/6D/actions/runs/40161774801). A public working URL, real TLS, provider billing and production observability remain separate evidence requirements.

[Build F acceptance](BUILD_F_ACCEPTANCE.md) · [Current scope](HACKATHON_BUILD_SCOPE.md) · [Local connection guide](REMEMBERED_SERVICE_CONNECTIONS.md)

## Reproducible Linux/container checks

`.github/workflows/hosted-checks.yml` runs the scoped hosted tests on Ubuntu, parses Compose, builds the image and exercises a constrained non-root container through invitation login, an already calculated reference, blocked owner routes, restart persistence and sign-out. It uses synthetic secrets and no model provider. The CI-only application port is mapped to runner loopback; the deployment recipe exposes only the HTTPS proxy. A green CI run does not establish public DNS/TLS, cloud costs or deployed inference. See BUILD_F_RESULTS.md for actual recorded execution status.
