# 6D v0.2.0 local release

Verified October 20, 2026. The main workspace runs at
http://127.0.0.1:8768/ with build **a36c689412a9**, using the project's own
environment backed by independently installed **Python 3.14.7**. Codex is not
required to run it. The versioned source snapshot is `v0.2.0-local`.

## Delivered

- **Setup-6D.cmd**, **Open-6D.cmd** and **Stop-6D.cmd** use installed Python or
  the project environment, without a Codex runtime path or package downloads.
  Stop uses an idle-server, same-origin endpoint and refuses other checkouts.
- Optional **Remember on this device** stores a Windows current-user encrypted
  API key. Startup restores it without an inference call. **Forget saved key**
  removes the saved copy and retains the current session; **Disconnect & forget**
  clears both. Environment-provided keys retain their documented precedence.
- A stopped-app backup/recovery tool preserves project history, configuration,
  model selection and the existing spending ledger together. It excludes keys,
  uses validated SQLite snapshots and restores only into a new directory.
- The [handover guide](RELEASE_HANDOVER.md) covers installation, opening, updating,
  the demo, troubleshooting, actual capabilities and remaining limitations.
- The previous [change-direction correction](CHANGE_DIRECTION_RESULTS.md) is
  included in this source snapshot. Its offline acceptance is not a new live-model
  validation result.

The encryption implementation follows Microsoft's current-user
[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
and [CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata)
interfaces. This is local credential storage, not authenticated team hosting.

## Measured verification

- **144 affected regression tests passed** under installed Python 3.14.7. This
  includes native encryption, restart restore, failure handling, strict APIs,
  shutdown, safe backup, project guards and the direction correction. It is not a
  claim that the full project suite was rerun.
- **17 launcher checks passed** after a real clean-start test exposed a too-short
  Windows loopback-refusal timeout. The timeout was corrected without treating
  genuinely unresponsive or foreign services as safe to replace. Counts overlap
  the affected regression suite.
- **Five browser connection groups passed**: opt-in/off by default, ciphertext
  without browser-stored key, restoration after restart, forget/session behavior,
  disconnect/no resurrection, narrow viewport and unchanged project/budget state.
  All used a synthetic key and forbidden provider factory in an isolated store.
- **Five clean-checkout/recovery groups passed**: Setup, actual Open/startup,
  deterministic baseline calculation, guarded Stop and actual private backup
  restoration in a new folder. The checkout path contained spaces, used installed
  Python, made no downloads and had no provider configuration or key.
- **Nine final read-only browser checks passed** on the main workspace with no
  browser errors, project changes, paid calls or model-selection changes.

The API fixture's cleanup initially left a test-owned SQLite inspection handle
open on Windows. It now closes that handle explicitly and waits for its worker;
the complete affected run then passed. This was not resolved by ignoring the
cleanup error or weakening the existing no-secret assertions.

Evidence: `work/self-contained-verified-regression.log`,
`work/portable-launch-tests.log`, `work/release-connection-browser.json`,
`work/clean-release-verification.json`, `work/release-current-browser.json`,
`work/self-contained-preservation.json` and the screened aggregate
[release evidence summary](RELEASE_EVIDENCE.json). Raw private artifacts remain
excluded from Git. The local-only actual-receipt tests are skipped when those raw
artifacts are absent; synthetic portable equivalents remain in source.

## Data and spending

A private, credential-free backup was created outside the repository and restored
into a new validation folder. Every saved table, configuration and historical
comparison artifact still matches that actual stopped-app backup. Its eleven
local runs include a later recorded run beyond the older ten-run comparison
baseline; the original ten records and that later record were all retained.

**No paid requests** occurred. Cumulative conservative reservations remain
**USD 2.30350988 of USD 29.50**. These are not verified billed charges. Super's
selection and global Nano configuration remain unchanged. Actual credentials
were not read, saved or migrated as a test; remembering remains your explicit
choice in the application.

## Remaining limits

The application still has seven bounded engineering models. It does not verify
an entire rocket, predict every failure or authorize launch. The latest live AI
comparison remains three constructed cases, with the historical Super semantic
error preserved. This release adds no new paid evaluation, model routing or
physics. Independent human engineering/user review, a larger live evaluation,
production authentication/hosting and the broader roadmap remain unfinished.

This is a local source release, not a deployed website or standalone Python-free
installer. Windows received native launcher/encryption verification; other
platforms retain session-only keys and have not received equivalent native tests.
