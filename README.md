# 6D

6D is a local engineering-evidence workspace for space projects. It connects
requirements, bounded calculations, revisions and test evidence so engineers can
inspect what was checked, what changed and what remains unassessed.

This is a working research application, not complete rocket verification or a
flight-readiness certification tool. AI explanations do not replace recorded
engineering findings.

## Run on Windows

1. Download or clone this repository into a permanent writable folder. Extract a
   downloaded ZIP first.
2. Install Python **3.10 or newer** if needed.
3. Double-click **Setup-6D.cmd** to create the project's local Python environment.
4. Double-click **Open-6D.cmd** and open [6D](http://127.0.0.1:8768/).
5. Choose **Guided review** for an explicit constructed example, or create/import
   your own supported project.

The core application uses Python's standard library. Setup requires no package
or model download, API key or paid request. It uses your installed Python and
project environment; Codex is not a runtime dependency.

Use **Stop-6D.cmd** before updating the source or taking a backup. It stops only
this checkout's idle server through a guarded local endpoint. Closing the browser
alone does not stop the server. Keep the project folder's `.local` data when
updating. Source updates can require local recalculation; historical records stay
preserved.

For other platforms, use Python 3.10+ and `python tools/open_preview.py` from this
folder. Optional remembered-key storage is currently Windows-only. These platforms
have not received the same native launcher verification as Windows.

[Installation, recovery, troubleshooting and demonstration guide](docs/RELEASE_HANDOVER.md)

## Working capabilities

- Project authoring/import, explicit systems and scalar interfaces, and immutable
  saved revisions.
- Canvas, Table and Reader views of shared records, plus reports and evidence
  JSON/print export.
- Targeted recalculation with source/dependency checks and recorded reuse.
- Seven maintained bounded models: ideal propulsion budgets, static cantilever
  loads, steady radiative equilibrium, one-condition drag, unforced three-dimensional
  two-body orbits, supplied power/energy budgets and single-axis PD attitude response.
- Explicit one-way calculation chains, hypothetical scenarios, supplied scalar
  CSV test comparisons and revision-scoped test applicability.
- Saved orbital playback and graphs of recorded trajectories, with accuracy gaps,
  criteria and exclusions visible.
- Read-only Nebius Assistant investigations with captured sources, reproducibility
  checks, exact application-owned numerical evidence and qualitative AI commentary.
- Deterministic before/after change directions and bounded contradiction checks
  for new investigations. Historical explanations and outcomes remain unchanged.

## Optional Nebius connection

Local calculations, saved history and reports work without a key. A new installation
has no paid provider configuration by default. Existing users should preserve or
restore their approved configuration **and reservation ledger together**. See
[provider setup](docs/PROVIDER_SETUP.md) and the handover guide; never reset a ledger
or change approval IDs to bypass the spending allowance.

Enter your key privately in **Connect AI**. **Remember on this device** is optional
and off by default. On Windows it saves a current-user encrypted copy so a later
startup can restore the connection. **Forget saved key** removes that copy while
leaving the active session connected; **Disconnect & forget** clears both. An
explicit `NEBIUS_API_KEY` environment variable takes precedence and must be removed
from the launch environment to prevent its use on later starts.

Starting, restoring or connecting makes no inference call. Only an explicit
investigation or approved comparison spends the configured allowance. Never put
keys in project inputs, chat, GitHub, screenshots or reports.

## Evidence and limitations

[Model applicability audit](docs/MODEL_APPLICABILITY_AUDIT.md),
[published-reference checks](docs/PUBLISHED_BENCHMARK_RESULTS.md) and
[targeted/full recalculation verification](docs/RECALCULATION_VERIFICATION_RESULTS.md)
describe measured checks and their boundaries. Optional external reference tools
are separate from the dependency-free application runtime.

The [latest live comparison](docs/APPLICATION_ROLES_LIVE_RESULTS.md) preserves
Nano's first-action failure and skipped cases, Super's incorrect direction wording
and Ultra's completed explanations. Automated completion is not semantic approval.
The [offline direction correction](docs/CHANGE_DIRECTION_RESULTS.md) catches that
actual Super error under a separately versioned policy without rewriting history.

These are AI-authored development cases and reference checks, not customer,
independent-human or complete aerospace validation. Scalar chaining is not a
simultaneous multiphysics solver. Orbital playback is not a full launch-to-landing
simulation. Expected conditions, applicability, uncertainty and excluded physics
remain engineering review questions. No finding authorizes launch or guarantees
mission success.

## Backup and recovery

Stop 6D first. From PowerShell in the project folder:

```powershell
.\Stop-6D.cmd
.\.venv\Scripts\python.exe tools/backup_local.py backup --output "C:\6D-Backups\sixd-backup.zip" --confirmed-stopped
```

Create the destination parent folder first. Backups contain private project data,
configuration and the existing spending ledger. They exclude remembered credentials,
logs and caches. Keep them private and outside Git. Restore only into a new data
folder using the instructions in the handover guide; existing data is never
silently overwritten. Do not use old backups to reduce recorded spending.

## Development

```console
python -m unittest discover -s tests
python run.py project-demo
```

Tests and examples use isolated constructed cases. Windows-specific tests run only
where native support is available; local raw evaluation artifacts are intentionally
excluded from Git and source archives. The demonstration command writes constructed
receipts under `artifacts/`; it makes no paid model call.

The active scope and remaining roadmap are recorded in [PROJECT_BRIEF.md](PROJECT_BRIEF.md)
and [RELEASE_PLAN.md](RELEASE_PLAN.md). The latest source snapshot includes the
current app, tests, examples and documentation; private `.local` data is separate.
