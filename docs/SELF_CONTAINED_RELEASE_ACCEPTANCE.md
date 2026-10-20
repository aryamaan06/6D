# Self-contained release acceptance

October 20, 2026. Arya explicitly authorized the proposed remembered connection,
independent startup, backup/recovery handover and final GitHub update. Acceptance
recorded before integration. No paid model calls are authorized by this milestone.

- Remembering a Nebius key is explicit, optional and off by default. Windows
  current-user DPAPI encrypts the local saved copy; no plaintext key enters Git,
  browser storage, logs, database receipts, status responses or release evidence.
- Restart restores a remembered key without making a provider request. Corrupt or
  unavailable credential storage fails with controlled, non-secret status. Forget
  removes the encrypted saved copy; disconnect also prevents a saved-key restore.
  Environment-provided keys retain their explicitly documented precedence.
- The existing connect API remains compatible. Strict request validation,
  local-origin restrictions, job/session guards and cumulative allowance remain.
- A fresh checkout with an independently installed Python can set up/start 6D
  without a Codex runtime, key, cloud account, package download or paid request.
  Paths containing spaces and controlled startup failures are tested.
- Backup preserves the workspace, recorded history/configuration and budget
  ledger, excludes credentials and validates a manifest. Restore defaults to a new
  destination, rejects invalid archives and never overwrites existing projects.
  Backup consistency conditions and machine-bound key limitations are explicit.
- Verify synthetic remember/connect/restart/forget/disconnect through backend and
  browser/API tests. Use isolated stores and keys. Do not save, access or migrate
  Arya's real key as a test; do not restore over the founder workspace.
- Publish clear installation, opening, backup/recovery, demo and known-limit
  instructions. Preserve current history and the Super interpretation exception.
- Run meaningful affected tests, a clean-checkout smoke test and final read-only
  saved-workspace verification. Restart only after production sources stabilize.
- Scan the complete commit for secrets/private data, push the verified source
  and release instructions to the authorized GitHub repository, and confirm the
  remote commit matches. No deployment, paid request or whole-platform completion
  is implied. A tagged source snapshot is not a hosted public service.

Measured results will be recorded separately, including any limitations in the
fresh-install, cryptographic, backup or UI checks.
