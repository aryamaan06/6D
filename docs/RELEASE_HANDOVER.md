> October 25 Build E: optional Windows-encrypted remembering is now available separately for Tavily and LangSmith. Service settings restore locally; prior reservations and explicit upload approvals remain. Keys stay out of backups. [Current connection guide](REMEMBERED_SERVICE_CONNECTIONS.md) · [Verification](BUILD_E_RESULTS.md). Earlier session-only statements below describe the previous implementation.

# Running and recovering 6D

This guide covers the local 6D application. The code and deterministic engineering
calculations run on your computer. Live Assistant investigations additionally need
a valid Nebius connection and the existing approved spending configuration.
Codex is a development tool, not an application runtime requirement.

## First installation

1. Download or clone the repository into a permanent folder you can write to.
   Extract a downloaded ZIP before launching it. Avoid moving the folder while
   the app is running.
2. Install a normal Windows Python **3.10 or newer** if one is not already
   available. The launcher uses your local installation or this project's virtual
   environment; it does not require the Codex bundled Python. If Windows opens
   the Store instead of running Python, install Python and rerun setup.
3. Double-click **Setup-6D.cmd**. Read its result. Setup creates the local project
   environment; the core application uses Python's standard library and does not
   require paid packages or a model call.
4. Double-click **Open-6D.cmd**. Open or bookmark
   [http://127.0.0.1:8768/](http://127.0.0.1:8768/).
5. Check the footer's build identity. Use **Guided review** for the constructed
   first-use walkthrough. Local checks work without an API key.

Run the `.cmd` files from File Explorer. Clicking them in an editor may open their
source instead. Keep this folder and its `.local` data when updating source code.

## Returning to the application

After a Windows restart, double-click **Open-6D.cmd**. Closing a browser tab does
not stop the background server. Refresh the page after an update. If an older
server is still running, use **Stop-6D.cmd**, then **Open-6D.cmd**. Stop waits for
an idle 6D server; it does not kill an unrelated process using the same address.
Finish active investigations before stopping.

Unsaved drafts belong to the current browser workflow. Save or discard them
explicitly before closing or switching projects. Saved projects, immutable
revisions, runs and investigations remain in `.local/workspace.sqlite3`.

## The API connection

Enter the key only in **Connect AI**. Do not paste it into chat, source files,
GitHub, screenshots, reports or project input fields.

- A session-only connection is held in server memory and is cleared by a backend
  restart.
- **Remember on this device** is optional. On Windows, it encrypts the remembered
  key using the current Windows account. It is not saved as plaintext in a project
  or configuration JSON. Startup can restore that private connection without
  making a model call.
- **Forget saved key** removes the remembered copy; a currently active connection may
  remain usable for that session as the UI explains.
- **Disconnect** clears the active key and removes its remembered copy. It will
  not silently reconnect from that saved copy at the next startup.
- A remembered key is not a portable backup. After recovery on another computer
  or Windows account, reconnect privately using your provider account's key.

An explicitly configured `NEBIUS_API_KEY` environment variable takes precedence on startup. Remove it from the launch environment to prevent that source from restoring a connection after disconnecting.

Connection, browsing, deterministic checks, historical viewing and exports do not
by themselves start paid inference. Start an investigation deliberately. The
development allowance and reservation history are separate from the provider's
account balance. Do not delete or reset `.local/budget.sqlite3` or change approval
IDs to obtain more allowance. Failed requests may retain reservations.

## A short demonstration

Allow about ten minutes; this is a procedure, not a measured usability claim.

1. Open **Guided review** and explicitly create a constructed reference project.
   Read its assumptions and exclusions; it is not a real flight design.
2. Run the baseline checks. Inspect a requirement's result, exact metric and
   declared limit. A satisfied component criterion is not mission authorization.
3. Create a shared draft and change one input using a sourced value, or use the
   clearly labelled demonstration value suggested by the guide. Preview impact.
4. Save a new revision and rerun affected checks. Show the changed finding and
   reused unrelated evidence. The old revision stays unchanged.
5. Open **Report**, inspect the explicit unassessed/excluded scope, export the
   evidence JSON and optionally print to PDF using the browser.
6. Optional, only with the private connection and approved allowance: select a
   requirement and start an Assistant investigation. Inspect its exact evidence,
   source links and qualitative explanation separately. New investigations show
   application-derived before/after directions and can reject contradictory prose.
7. Optional: use the orbital reference and view its saved 3D trajectory. Playback
   shows recorded model output; it is not a full launch-to-landing simulator.

## What is currently supported

The seven maintained bounded models cover ideal propulsion, static beam loading,
steady radiative equilibrium, one-condition atmospheric drag, unforced 3D two-body
orbit propagation, supplied power/energy budgets and single-axis PD attitude
response. Their assumptions and limits are part of their evidence. Scalar links
between calculations are explicit one-way transfers, not simultaneous multiphysics.

Other working features include project/revision authoring, system and interface
organization, targeted recalculation and evidence reuse, hypothetical scenarios,
supplied scalar test-data comparison, reports, source-linked read-only Assistant
investigations and orbital playback. This is not complete rocket verification,
flight certification, high-fidelity CFD/FEA, full GNC or a guaranteed readiness
assessment. Missing evidence must remain visible.

The historical Nano/Super/Ultra evaluation records include failures and skipped
cases. In one completed historical Super explanation, a decreased temperature
limit was incorrectly called an increase. The new change-direction guard catches
that specific error in a separate offline reassessment; the original receipt and
score were not rewritten. Ultra completed the narrowed three-case comparison
with more specific explanations, but that is not general engineering validation.
See [change-direction results](CHANGE_DIRECTION_RESULTS.md) and
[live comparison results](APPLICATION_ROLES_LIVE_RESULTS.md).

## Back up local data

An evidence JSON export is useful for sharing a finding, but it is not a full
application backup. A recovery backup must preserve the project database,
provider settings, model selection and spending ledger together. Archives can
contain private engineering data and untrusted user-entered text. Keep them
private; this tool is not a general secret scrubber or encrypted file vault.

1. Save/discard drafts and wait for active work to finish.
2. Run **Stop-6D.cmd**. Stop any other process using this `.local` folder. Closing
   the browser alone is insufficient.
3. Open PowerShell in the project folder and run the following, choosing a new
   output filename if one already exists:

   ```powershell
   .\.venv\Scripts\python.exe tools\backup_local.py backup --output "$env:USERPROFILE\Documents\6D-backup-2026-10-20.zip" --confirmed-stopped
   ```

4. Read the success result and keep the archive outside the project folder, for
   example on a private backup drive. Restart with **Open-6D.cmd**.

The tool refuses an active listener on port 8768 and requires your confirmation
that all database users have stopped. It uses SQLite's backup API and integrity
checks rather than copying only a database's main file while omitting committed
WAL records. Multiple database snapshots require a stopped app; a successful
individual SQLite snapshot alone does not prove a coordinated live backup.

The strict backup allowlist is:

- `workspace.sqlite3`;
- `budget.sqlite3` together with `token-factory.json`, when configured;
- `project-assistant-model.json`, when present.

The archive contains a digest/size manifest. Remembered credentials, `.env`, logs,
caches, evaluation scratch folders and arbitrary local files are excluded. A
digest detects file changes; it is not a signature proving who created an archive.
Use backups you trust.

## Recover into a new checkout

Restore never overwrites an existing `.local` folder. Do not erase a spending
ledger to make a restore proceed, or operate old/new copies as separate allowances.

1. Keep the original folder unchanged. Download/extract the matching source
   checkpoint into a new folder, for example `C:\6D-Restore`.
2. Run **Setup-6D.cmd** in that folder. Do **not** open 6D yet; its `.local` restore
   destination must not already exist.
3. Stop any running 6D server. In the new folder's PowerShell, run:

   ```powershell
   .\.venv\Scripts\python.exe tools\backup_local.py restore --archive "$env:USERPROFILE\Documents\6D-backup-2026-10-20.zip" --to "C:\6D-Restore\.local" --confirmed-stopped
   ```

4. Read the success result, then launch the recovered checkout with **Open-6D.cmd**.
   Check the project list, historical revisions and allowance/reservations before
   starting a new live investigation.
5. Reconnect the API key privately if needed. It is intentionally absent from the
   backup. Once recovery is verified, keep the old folder archived and stop using
   its independent local ledger.

Archive validation rejects missing settings/ledger pairs, mismatched approval or
cap, changed file digests, unsupported paths, duplicate entries, links and files
over the supported size bounds. Restore validates in a temporary directory, then
moves the validated bundle into the new destination. It does not merge projects
or reconcile two divergent spending ledgers.

## Troubleshooting

| Symptom | Action |
|---|---|
| Site cannot be reached | Run Open-6D.cmd; read its result. Check `http://127.0.0.1:8768/`, not an old port. |
| Python missing or unsupported | Install Python 3.10 or newer, then rerun Setup-6D.cmd. |
| Older 6D occupies the address | Finish active work, run Stop-6D.cmd for that checkout, then open the intended checkout. Do not stop an unrelated process blindly. |
| Key is not connected after restart | Session-only keys are cleared. Connect privately; optionally remember the key on this Windows account. |
| Remembered key cannot be restored | Reconnect privately or forget the saved copy. Restoring a backup does not restore credentials. |
| Live Assistant is unavailable | Local checks still work. Review connection, provider configuration and the existing allowance; do not reset the ledger or retry a paid batch repeatedly. |
| New revision has no result | Run affected checks explicitly. Saving is not calculation or verification. |
| Backup says server is active | Stop the background server; closing the browser is insufficient. |
| Restore says destination exists | Use a separate new checkout/destination. Preserve the existing data; restore does not overwrite or merge it. |

Keep startup logs private. They help diagnose local startup failures; keys should
not be entered in command lines or file-based configuration. When asking for help,
share a controlled error/build ID, not keys or private project data.

## Continued work

The next priorities are independent engineer/user review, repeatable human-graded
live AI evaluation, a more convenient engineering intake format and validated
capabilities driven by real project needs. Hosted/team operation needs its own
authentication, access control, backup and data-governance work. Broad claims of a
complete launch-to-landing platform are not supported by this local release.
