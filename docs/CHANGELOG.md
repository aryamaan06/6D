# Historical development notes

Archived README snapshot before the October 24 review corrections. Dates, build IDs, counts and pending statements below describe their own checkpoints; use the current README and validation index for current status.

# 6D

October 24 live AI qualification (build `a3da59c91ebc` at http://127.0.0.1:8768/): current-model four-case qualification and optional LangSmith metrics export are delivered locally. Nemotron Super completed all four constructed cases with 16 accepted live responses, USD0.1704048 reserved; the earlier HTTP401 receipt/one reservation remains unchanged after an explicitly authorized fresh batch. Separate coding-agent AI review found no material prose error in these four explanations, with minor omissions recorded; this is not independent human or general engineering validation. LangSmith accepted one explicitly approved sanitized metrics upload; keys/prompts/engineering values were excluded. Tavily is now connected and live-qualified: one Basic search returned five NASA references, reserved/reported one credit, and preserved exact unsaved reference-form provenance. Six live browser groups and 22 focused regression tests passed again without further credit use. No source/link/finding or Nebius budget changes occurred; only append-only search receipts were added. See docs/TAVILY_LIVE_RESULTS.md. The earlier pending Tavily status is superseded. Current cumulative ceiling USD29.50/reservations USD2.47998038 and model selection are preserved. All original workspace rows/configs match the baseline; 247 distinct affected tests passed, plus isolated/integrated/mobile browser checks. See docs/AI_QUALIFICATION.md and docs/AI_QUALIFICATION_RESULTS.md. Four agreed build implementations are delivered; final corrections/deployment/submission is the remaining milestone and requires its own start instruction. No GitHub push or hosted application deployment occurred. Earlier checkpoints are historical.

Latest local build: **Connected review and interface polish** (`33affdca8bf9`, October 24). Refresh the app to open **Review overview**, filter recorded findings, inspect their assumptions and follow links to coverage, simulation, studies, actions or the full report. **Analysis tools** groups the existing simulation/study/import/test views. SI powers display as superscripts while raw tokens and exports stay exact. [Guide](docs/CONNECTED_REVIEW.md) · [Delivery evidence](docs/CONNECTED_REVIEW_RESULTS.md). No key is needed. Previous delivery notes follow.

Latest local build: **Operating-envelope studies** (`395f0632f981`, October 23). Open **Envelope studies**, enter justified parameter ranges, **Preview exact grid**, then explicitly run/save it. Inspect worst observed margins, tied cases and unresolved findings. These are sampled observations, not continuous safety bounds. [Guide](docs/OPERATING_ENVELOPES.md) · [Delivery evidence](docs/OPERATING_ENVELOPES_RESULTS.md). No API key is required. Earlier deliveries follow.

Latest local build: **Specialist simulation imports** (`3eed1f8127d9`, October 23). Open **Simulation imports → Use constructed CSV example → Validate & preview CSV → Save reviewed import**. Replay recorded samples, declare units/frame/configuration, and optionally compare compatible fields with a frozen orbital or vertical-flight calculation. [Guide](docs/SIMULATION_IMPORTS.md) · [Delivery evidence](docs/SIMULATION_IMPORTS_RESULTS.md). No key is required. Earlier delivery notes follow.

Latest local build: **Numerical accuracy** (`a6215d46280d`, October 23). New orbital runs use RK4 with retained grid checks; saved older runs keep their original evidence. Open **Simulation → Project evidence → Open orbital review template**, explicitly create the reference project, then **Run affected checks**. [User guide](docs/NUMERICAL_ACCURACY.md) · [Measured results](docs/NUMERICAL_ACCURACY_RESULTS.md). No key is required. Earlier delivery notes follow.

Latest local build: **Powered vertical flight** (`cedf1afe772d`, October 23). Open **Powered flight → Use constructed flight reference → Create project**, then **Powered flight → Run checks** to inspect saved ascent/coast, burnout and six charts. [User guide](docs/POWERED_FLIGHT.md) · [Delivery evidence](docs/POWERED_FLIGHT_RESULTS.md). This is the eighth bounded model; steering, staging and landing remain outside its scope.

**Engineering coverage** maps mission checks, records model-fit rationale, exposes missing analysis and flags declarations after changes. [User guide](docs/ENGINEERING_COVERAGE.md) · [Delivery evidence](docs/ENGINEERING_COVERAGE_RESULTS.md).

The local **Source library** now feeds pinned references into new saved-requirement investigations, with optional explicit Tavily search and preview before manual intake. See [the source-connected Assistant guide](docs/SOURCE_ASSISTANT.md) and [offline verification results](docs/SOURCE_ASSISTANT_RESULTS.md). Live qualification of the new source-aware workflow is pending.

The local **Compare designs** view compares pinned saved runs and hypothetical cases, with criterion margins, evidence gaps and exact captured exports. See [the comparison guide](docs/DESIGN_COMPARISON.md) and [verified results](docs/DESIGN_COMPARISON_RESULTS.md).

The local **Engineering actions** board tracks follow-up from findings and source-review flags, with versioned workflow, supporting records and change flags. See [the action guide](docs/ACTION_QUEUE.md) and [verified results](docs/ACTION_QUEUE_RESULTS.md).

The local **Source library** connects versioned manual references to requirements, assumptions and saved findings, with review flags and report exports. See [the source-library guide](docs/SOURCE_LIBRARY.md) and [verified results](docs/SOURCE_LIBRARY_RESULTS.md).

Project spreadsheet intake is available through **Import project → Import CSV / Excel**, with a downloadable constructed example. See [the intake guide](docs/SPREADSHEET_INTAKE.md) and [verified results](docs/SPREADSHEET_INTAKE_RESULTS.md).

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
- Eight maintained bounded models: ideal propulsion budgets, static cantilever
  loads, steady radiative equilibrium, one-condition drag, unforced three-dimensional
  two-body orbits, supplied power/energy budgets, single-axis PD attitude response,
  and powered vertical ascent/coast with mass depletion and atmospheric drag.
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
