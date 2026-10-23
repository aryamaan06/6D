# Spreadsheet project intake — October 20, 2026

Delivered locally at http://127.0.0.1:8768/, build `bfc0c02cccab`. October 30 is the active submission deadline; October 21 is not a handover or scope deadline.

## Delivered behavior

Import project → Import CSV / Excel opens a local, explicit mapping workflow for supplied inputs, direct model-parameter bindings and declared requirements. It accepts values-only `.xlsx` or UTF-8 CSV. A constructed Excel workbook and three CSV templates are downloadable inside the dialog.

Preview reparses the original bytes, reports row/mapping/unit/schema issues and shows canonical records before any save. Editing metadata or mappings invalidates that preview. Creation uses the existing new-project transaction, refuses an existing ID and produces R1 without a calculation. Run checks remains the separate explicit action that generates maintained engineering evidence.

Original source labels are preserved. The project description also retains a clearly labelled import manifest with filenames, byte hashes and exact sheet/column mappings. This is provenance for the supplied bytes, not authentication or validation of their contents. Uploaded files are not copied into browser persistence or sent to a third party; the saved project contains the mapped records and manifest, not the original workbook bytes.

## Verification

- All 195 affected regression tests passed, including 17 intake parser/validation groups and five intake HTTP workflow tests. This was an affected regression run, not a claim that the whole repository suite was rerun.
- Six real-API Chrome workflow groups passed: example download; incompatible-unit rejection; corrected mapping and stale-preview invalidation; explicit save then 100 N drag calculation against a declared 150 N limit; real Excel workbook intake; mobile/Escape behavior. No page errors or external requests occurred.
- Eight isolated UI groups with 13 assertions passed, including stale asynchronous responses and failed replacement uploads. These overlap the real workflow coverage and are not additional independent engineering validation.
- Seven final read-only checks passed on the delivered main application with no attempted writes, external requests or page errors.
- An independently authored artifact-tool workbook was rendered and inspected on all three sheets. CSV and XLSX imports preserve matching engineering records; their source-specific provenance manifests differ. The existing drag calculator agrees with the independently hand-evaluated 100 N example.
- All existing local database rows, configurations and selected historical artifact hashes match the milestone baseline. That baseline contains 12 saved runs; a later run beyond the preceding release's 11-run snapshot was already present and was retained.
- No paid requests, model activation or allowance change. The existing cumulative USD 29.50 ceiling and USD 2.30350988 conservative reservations are unchanged; reservations are not billed usage.

Private validation receipts and screenshots remain in ignored `work/`: `spreadsheet-intake-regression.json`, `intake-browser-results.json`, `spreadsheet-ui-isolated.json`, `intake-current-application.json`, and `intake-baseline.json`.

## Material limits

Files are bounded to 1 MiB each, 1.5 MiB combined, three files, twelve worksheets, 500 data rows per sheet and 32 columns. Selected formulas/cached formula results, merged cells, unsafe archives, unsupported date/percentage values and legacy or macro formats are refused. Numeric values use finite machine arithmetic; plain integers outside the browser's exact integer range are refused. This is a defined intake layout, not automatic interpretation of arbitrary engineering workbooks. Use text cells for identifiers; display formatting is not an imported unit or identifier definition.

The scalar sheet layout does not encode power operating profiles, calculation chains, system interfaces or orbital accuracy criteria. Their existing editors/structured JSON remain available. Orbital requirements without explicit accuracy criteria remain unassessed. No new physics model, formula execution, automatic unit conversion or hardware-validity claim is added.

Tavily and LangSmith are not connected by this milestone.
