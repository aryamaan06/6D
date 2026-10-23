# Import a project spreadsheet

Open 6D at http://127.0.0.1:8768/ and choose spreadsheet import from Open an engineering project. This creates a new project from supplied engineering records. Test measurement comparison remains a separate workflow.

1. Start with `examples/project-intake/constructed-drag.xlsx`, or upload the three CSV example files. The example data is synthetic, with no claim of measured hardware performance.
2. Select the sheet/file for each of Inputs, Bindings and Requirements. Map the columns explicitly. The header row must be the first row.
3. Enter a new project ID, name, description and lifecycle stage. A stage is descriptive metadata; choosing physical test or operation does not establish physical evidence.
4. Preview the import. Review all records, units, mappings, sources and validation messages. Correct the original file or column mapping when needed, then preview again.
5. Choose Create project. This saves the project without calculating results. Choose Run checks in the existing workspace when ready.

## Three tables

| Table | Required columns | Meaning |
| --- | --- | --- |
| Inputs | `id`, `value`, `unit`, `source` | One finite numeric quantity per row, with exact unit and supplied provenance |
| Bindings | `model_id`, `model_type`, `parameter`, `input_id` | One explicit model parameter binding per row; repeat the model ID and type for its other parameters |
| Requirements | `id`, `title`, `model_id`, `metric`, `operator`, `limit_input`, `critical` | One declared scalar criterion per row; `critical` is explicitly `true` or `false` |

IDs and references must match exactly. Numeric values use decimal points or scientific notation without thousands separators. Units use the maintained internal spellings, including `m/s`, `m^2`, `kg/m^3` and dimensionless `1`. Operators are `<=`, `>=` or `==`. 6D does not guess models, sources, missing quantities or unit conversions.

The saved project description retains the supplied description and an import manifest listing filenames, source-byte SHA-256 hashes, selected sheets and column mappings. This records which files and mappings produced the project; it does not authenticate the source data or validate the engineering. Equivalent CSV and Excel records can produce the same numerical inputs and criteria while retaining different import manifests.

## File limits and scope

Use UTF-8 CSV or ordinary `.xlsx` workbooks. Files are limited to 1 MiB each and 1.5 MiB combined, with at most three files, twelve sheets, 500 data rows per sheet and 32 columns. Encrypted workbooks, `.xls`, `.xlsm`, selected sheets with formulas or merged records, and unsupported cell types are not imported. To import reviewed formula outputs, create a values-only copy yourself and retain its calculation provenance in the source column.

Keep identifiers with leading zeros as Excel text. Decimal/scientific quantities use the application's finite floating-point representation. Plain integer literals outside the browser's exact range of ±9007199254740991 are rejected.

This layout supports direct scalar model bindings. Configure power operating modes, system interfaces, calculation chains and orbital accuracy criteria in the existing workspace editors, or use structured JSON for those complete records. An orbital import without accuracy criteria remains diagnostic and its requirements remain unassessed. A valid import does not establish the physical suitability of supplied data or models.

The constructed drag example calculates 100 N against a supplied 150 N maximum after Run checks. It represents one atmospheric condition only; drag coefficient applicability and a complete vehicle are not verified.
