# Project authoring acceptance

Implementation and regression tests: October 17, 2026. Delivery rechecked October 18, 2026, Asia/Calcutta. Build **db83df98ea99** at http://127.0.0.1:8768/.

## Delivered workflow

New project creates a supplied empty saved R1. Author project uses the shared draft to add/edit/remove explicit inputs, supported model definitions and parameter bindings, requirements and project metadata. The maintained catalog supplies exact units, metrics and scope without numerical defaults. Setup validation checks record/mapping completeness without executing physics. Existing impact preview, immutable save, targeted calculation/reuse, reports, investigations and orbital playback use these same records.

Referenced records cannot be silently deleted. Missing values cannot become zero. IDs remain stable after addition. Definition additions/removals/edits and metadata changes appear in Changes. Before any engineering run exists, the comparison uses the preceding saved configuration and labels it accordingly. Empty skeletons have no passing review, receipt or evidence report; strict numerical review validation retains its nonempty contract.

See [PROJECT_AUTHORING.md](PROJECT_AUTHORING.md) for the procedure, contracts and limitations.

## Verification

- The final full repository suite passed **486 tests** in **91.258 seconds**, using `python -m unittest discover -s tests`. Output is retained in ignored `work/project-authoring-tests.log`.
- Twelve authoring contract/storage tests cover exact model metadata, no-calculation preflight, empty persistence/no false pass, incomplete mappings, units, unsupported models, immutable additions/removals/reuse, and unreviewed revision baselines. Five new HTTP tests exercise the same intake/run/export boundaries through actual local requests.
- Existing lifecycle, workspace, physics, provider-budget, investigation, simulation and API regressions are included in the full suite. JavaScript syntax checks pass.
- The earlier full run had one Windows loopback connection-abort error in an unchanged legacy cross-origin test. All thirteen legacy local API tests passed on focused rerun, and the final full suite passed. No unrelated legacy API implementation was changed.

## Browser acceptance

`work/project-authoring-browser.json` records nine passing workflow groups in a fresh isolated database, through the actual forms:

1. Create a truly blank saved project and verify no run or passing review exists.
2. Refuse missing numeric input without converting it to zero.
3. Author eleven supplied inputs, two independent models and two requirements; protect duplicate IDs and referenced deletions.
4. Validate, preview, save and calculate. The independent supplied drag case agrees with the hand reference of 100 N; the supplied thermal case violates its declared criterion.
5. Remap only the thermal heat-input binding in a new revision. Only thermal reruns; the aerodynamic model preserves its original execution origin. Saved report/export share the canonical evidence.
6. Edit a requirement title/operator. The new criterion is assessed using reused calculations.
7. Show unit-mismatch setup errors and prevent selecting incompatible inputs for new bindings. Discard restores the saved revision.
8. Explicitly remove a requirement, its model and unreferenced inputs. Show the removed coverage in revision review and preserve historical evidence.
9. Reopen after reload, verify the original review remains identical, and inspect desktop/mobile authoring and the editor without document overflow.

The report PDF was generated and its extracted text verified against the exported canonical review identity and declared requirement. Desktop and 390-pixel mobile screenshots were visually inspected. Existing style is retained; final cosmetic refinement is still deferred.

The existing orbital engineering walkthrough also passed its ten browser groups on the same delivery build. That checks exact canonical playback, sample values, exports, requirement-scoped Assistant navigation, limit-only reuse, changed-orbit targeting, independent thermal targeting, comparison/history, exploratory independence, invalid-input abstention and reload. Its results are in ignored `work/orbit-workflow-acceptance.json`.

All browser calculations and record mutations used isolated temporary workspaces. No JavaScript errors, external requests or AI/investigation starts occurred. The first authoring browser attempts reached an older temporary QA server; acceptance was completed on a separate verified current QA port. A discovered gap in unreviewed change baselines was fixed and regression-tested before final acceptance.

## Saved data and delivery

The founder database was backed up under ignored `.local/backups/` before updates. After restart and read-only live inspection, all rows match the backup exactly: one project, one revision, six runs, two investigations, two model comparisons and one saved exploratory simulation. SQLite integrity is `ok`. Private provider/model configuration and the cumulative allowance ledger retain their earlier file digests. `work/authoring-migration.json` records this verification.

`work/live-authoring-smoke.json` verifies delivery build db83df98ea99 with `restart_required: false`, visible build identity, New project, read-only authoring guidance and the preserved saved simulation. Only read-only setup-preflight POSTs were allowed; no saved mutation or calculation occurred in that check.

No paid model calls, new provider selection, commit, push, deployment or publication occurred. A backend restart clears the memory-only API connection; local authoring/calculation/playback needs no key.

## Boundaries

Setup readiness is not an engineering verdict. Numerical domains, physical applicability, source accuracy, uncertainty and exclusions remain governed by the existing adapters and engineering review. This adds authoring for the existing five bounded models; it does not implement new physics, arbitrary solver execution, general custom system hierarchies, broader document/CAD ingestion, team security or whole-mission readiness.
