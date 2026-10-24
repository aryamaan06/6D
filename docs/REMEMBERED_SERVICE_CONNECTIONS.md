# Remember optional service connections

Build E, October 25, 2026. Open http://127.0.0.1:8768/ and refresh; delivered build **a8807e9db185**.

## Connect once on this Windows account

1. For Tavily, open **Source library → Optional Tavily connection**. Enter the Tavily key privately, select the approved absolute search-credit ceiling, check **Remember on this device**, and choose **Connect privately and set allowance**.
2. For LangSmith, open **AI quality & tools → Optional metrics in LangSmith**. Enter its own key privately, select the correct US/EU region and optional workspace UUID, check **Remember on this device**, and choose **Connect privately**.
3. Subsequent server starts restore each opted-in connection locally. An unchecked checkbox is the default for a new submission even when a saved key already exists. Read the connection status to see whether it is remembered.

Existing session-only keys are not silently saved. Re-enter each optional key once through its own form to opt in. Never place Tavily or LangSmith credentials in **Connect AI**, which is for Nebius. Nebius retains its existing independent remembering option and old storage format.

Connecting and restoring do **not** validate the key with its provider, make a search, upload metrics or run inference. A revoked key can restore locally and still fail on the next deliberate provider action.

## Remove or replace a connection

| Action | Current session | Saved encrypted copy | Earlier records and reservations |
| --- | --- | --- | --- |
| Forget saved key | Remains connected | Removed for this service | Retained |
| Disconnect and forget | Disconnected | Removed for this service | Retained |
| Connect with Remember unchecked | New session-only connection | Any previous saved copy removed | Retained |
| Restart after Forget | Disconnected | Absent | Retained |

Connection changes are blocked while that service has an active search/upload. A storage failure reports a controlled error and preserves the previous connection rather than claiming successful saving or removal. A storage error does not prove the saved copy is absent; refresh status and use the recovery controls. Other service connections are unaffected.

## Allowances and consent

Tavily remembers its approved **absolute** local credit ceiling, not a fresh allowance per restart. Every prior request reservation remains counted, including failed requests. An exhausted ceiling stays exhausted; a saved ceiling below existing reservations cannot activate a connection. Provider-reported overage still blocks research for review. This is an application reservation limit, not verification of the provider's remaining balance.

LangSmith remembers region and optional workspace UUID. It still uploads only the allowlisted qualification metrics after the user previews and explicitly approves that payload. It does not enable general tracing, automatic uploads or a new export allowance. Saved upload-attempt receipts remain authoritative.

## Storage and limits

Windows current-user DPAPI encrypts each service's key and validated settings with service-specific entropy and an encrypted service/schema identity. Atomic temporary files contain ciphertext only. The two new files are `.local/credentials/tavily.dpapi` and `.local/credentials/langsmith.dpapi` in the default local setup; custom private runtime directories remain supported. Do not publish or share these files.

Keys are not stored in browser storage, project JSON, reports, receipts or the repository. Existing allowlisted stopped-app backups exclude credential blobs. A restored backup requires reconnecting keys. Ordinary session-only connections remain available on unsupported platforms; there is no plaintext fallback for remembering.

This feature is for this local Windows user/device. It does not provide hosted secret management, authenticated team access, protection from malicious software already running as that user, or a portable credential backup. Build F hosting remains separate.

[Acceptance](BUILD_E_ACCEPTANCE.md) · [Recorded checks](BUILD_E_RESULTS.md)
