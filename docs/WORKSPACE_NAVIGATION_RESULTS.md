# Workspace navigation and typography — Build 1

October 25, 2026. Authorized workspace-navigation refinement plus the supplied Apple × Notion font specification. Delivered local build **ddf25eff8f3f** at http://127.0.0.1:8768/. No paid inference, search, upload or public deployment was performed.

## Changed

- Projects landing and five work areas replace the flat sidebar list. Area cards and contextual subnavigation preserve existing engineering, simulation, evidence, authoring and AI-quality destinations. Project actions are grouped in the header; the systems tree and view-mode tabs appear in their appropriate workspace.
- Breadcrumb parents, an in-app Back arrow and fragment-based browser history track saved project/revision, work area/tool, system, selected engineering item, view and context panel. Refresh and direct saved-view links restore that context. URLs never contain input values, draft contents, questions or credentials.
- Same-context navigation retains the shared draft. Switching saved context confirms before discarding changes; rejecting a browser traversal restores the current location. Loading a route locks mutations. Open authoring and thrust-profile edits receive explicit protection. Standalone exploratory forms are not persistent draft storage; see the guide's boundaries.
- Local native font stacks, tracked headings/labels, mono identities/quantities, off-white surfaces and subtle borders implement the requested typography without network font downloads. Large numerical findings remain prominent; essential small secondary instructions use a darker gray for readability.
- A real browser reload test exposed intermittent local static-resource connection refusals with the inherited five-connection accept backlog. The loopback server backlog is now 64. The hosted server's separate admission limits and backlog are unchanged. Refusals were not observed in the final browser run; this is not an arbitrary-network reliability guarantee.

## Verification

- Six Node browser-history contract tests passed, covering encoded identities, rejected malformed locations, deduplicated navigation, cancelled traversals and rapid asynchronous traversal.
- Two isolated HTTP/static-boundary tests passed, including dependency order, local-only assets, explicit asset serving and denial of private/repository paths.
- Fifteen existing workspace API regressions passed.
- Fourteen existing rocket-reference checks passed.
- Hosted regression discovery ran 46 methods: 45 passed, one environment-dependent check skipped. No full-suite rerun is claimed for this interface-only delivery.
- The final isolated browser run passed **17 groups**. It covered all five work areas, Back/Forward, historical-revision reload, Table/selected-item/Evidence context, shared-draft retention, accepted/rejected project traversal, delayed-load coherence, native type/mono styling and a 390-pixel viewport. Three additional groups verified that unapplied staged-profile fields survive blocked area/project/revision navigation and browser Back, and that explicit cancellation restores navigation without changing saved inputs. No browser errors, unexpected HTTP responses, external requests or provider calls occurred. Saved fixture project views matched their original snapshots; only read-only draft impact/linked-evidence previews were posted.
- The identified owner server was stopped through its guarded endpoint and restarted with the existing launcher. Health reports the current build and no restart required. Nebius, Tavily and LangSmith remembered keys restored with no credential error and no remote validation call. All five private database/credential objects in the before/after snapshot matched exactly (database table row identities/digests; credential ciphertext hashes). No raw data or key was published.

Browser receipts/screenshots are local under `work/navigation-browser/`; private owner-state digests remain under `work/`. Committed acceptance tooling uses isolated constructed projects rather than the founder database.

## Still separate

Three-model Nano/Super/Ultra selection, owner accounting-display changes, final current-source live AI qualification, later interface polish/founder walkthrough and actual public hosting remain separate. Super remains selected. Opening a destination does not start inference, a search or a metrics upload. No independent human usability or engineering validation is claimed.

[How to navigate](WORKSPACE_NAVIGATION.md) · [Acceptance](WORKSPACE_NAVIGATION_ACCEPTANCE.md)
