# Spreadsheet project intake acceptance

## User task

An engineer imports a supplied project spreadsheet, corrects a mapping or unit issue, previews the project and explicitly creates it. The existing Run checks action then calculates its findings. Neither import nor preview calls an AI provider.

## Acceptance cases

1. Import `examples/project-intake/constructed-drag.xlsx`, select Inputs, Bindings and Requirements, and confirm their column mappings. The preview contains five inputs, one drag model and one requirement with the original values, exact units and source descriptions.
2. Complete the same task with the three CSV example files. Their numerical inputs, model bindings and requirement criteria match the workbook import. Persisted provenance differs because the original files, byte hashes and sheet mappings differ.
3. Replace the speed unit `m/s` with `km/h`. Preview reports the specific incompatibility and does not allow creation through this intake. Correct the file to `m/s`, reimport and preview again. No automatic conversion occurs.
4. Change a mapping or project field after a successful preview. Creation remains disabled until a fresh preview succeeds. An older in-flight preview cannot re-enable creation for newer selections.
5. Before explicit Create project, project/revision/run counts remain unchanged. Creating a project records revision 1 with no calculated finding. Explicit Run checks produces drag force 100 N against the supplied 150 N maximum; hand arithmetic is `0.5 × 1 × 10² × 1 × 2 = 100 N`.
6. Reuse an existing project ID. Creation reports a conflict and preserves that project's revisions, findings and receipts. Canceling or closing intake does not change existing projects.
7. Blank required fields, duplicate IDs or parameter bindings, missing input/model references, nonfinite numbers, invalid Boolean values, duplicate or incompatible column mappings and unknown metrics produce specific preview issues. Values, sources, units and mappings are never inferred to repair them.
8. Selected Excel sheets containing formulas are refused even when a cached result exists. Explain that the user must supply reviewed values. Unsupported cell types, merged records, oversized sheets and malformed or unsafe archives fail with a controlled message. No workbook macros, links or formulas execute.
9. Uploaded cell content and filenames render as text. Quotes and HTML-looking values cannot inject markup. CSV and Excel data remain local; no storage to browser persistence or third-party service occurs.
10. Existing JSON/template intake, CSV measurement comparison, authoring, revisions, targeted reruns, history and AI connection controls remain usable. The maintained engineering model count stays seven; intake adds no physics or new engineering-validity claim.

## Boundaries

The first spreadsheet layout represents direct input bindings and declared scalar requirements. Power mode/load profiles, calculation chains, interfaces, systems and orbital accuracy settings are edited through their existing workspace controls or preserved through structured JSON. Importing orbital inputs without explicit accuracy criteria leaves orbital requirements unassessed. Import validity checks record structure and units; numerical domains and physical applicability remain subject to the existing engineering checks.

Record actual test/browser results separately after implementation. This document defines acceptance and does not claim these cases have passed.
