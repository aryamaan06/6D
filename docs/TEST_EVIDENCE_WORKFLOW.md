# Test evidence in the engineering workflow

Saved scalar test comparisons now appear beside their requirements in the Inspector and Evidence panel, in the selected system Reader, in the full Report, and in Changes. No calculation or inference runs when these views open.

## Try it

1. Open http://127.0.0.1:8768/ and select a saved project/revision. Run its supported checks if a current baseline is missing.
2. Open **Test data**, import your explicitly mapped CSV, declare its origin, observable and conditions, then save the comparison. The constructed example walkthrough is in TEST_DATA_COMPARISON.md.
3. Return to Table or Canvas and select a mapped requirement. Its linked test cards show the original design finding, measured criterion satisfaction and prediction agreement separately. **Open original comparison** selects that exact saved CSV row.
4. **Investigate comparison** opens the Assistant scoped to one recorded row. Review the selected row before choosing **Start live investigation**. Start sends that row's frozen original requirement, scalar model evidence, conditions, source identities and current applicability context with the question. It uses the existing on-request provider and spending controls. Opening the panel sends no inference request.
5. Edit a bound input or requirement in the shared draft and open **Changes**. The applicability preview marks affected evidence while retaining the old measurement, prediction and criterion. Save and rerun supported checks as appropriate; an old physical test is never rerun or reinterpreted automatically.
6. Open **Report** for the complete saved configuration. **Export combined review JSON** includes the canonical workspace, linked comparisons and original submitted CSV sources. **Export evidence JSON** remains the canonical calculation export. **Print report / Save PDF** includes the linked cards and expanded provenance.

## Applicability labels

| Label | Meaning |
| --- | --- |
| Exact reviewed baseline | The comparison belongs to the selected current saved run and matching dependencies/sources. Supplied test conditions remain unverified. |
| Dependencies unchanged | Original requirement, bound model/input/criterion records, relevant adapter and sources match. The comparison remains historical; it is not a repeated test or automatic approval for a later revision. |
| Applicability needs review | Recorded dependencies, sources or current evidence differ. Original outcomes remain visible against their own baseline. |
| Requirement removed | The selected configuration no longer includes the original requirement. Changes and the full Report retain the historical row. |
| Unmapped requirement | The original CSV row had no matching baseline requirement. A new requirement with the same ID cannot retroactively map it. |

The read-only projection covers the latest twenty comparisons at or before the selected revision, before requirement filtering. It discloses when older records lie outside the window. Open Test data for its separate saved-history view. The full Report and combined JSON retain removed and unmapped rows within this window; a selected requirement/system view filters to that selection. Counts describe evidence links or recorded discrepancies, never mission readiness or a percentage of physical validation.

## Evidence boundaries

Measurement compliance and prediction agreement remain separate from canonical calculated findings. A measurement can exceed its requirement while still agreeing with the model within the declared tolerance. Each saved row retains its original baseline, own criterion, source CSV/hash, conditions declaration, provenance and recorded next checks.

Applicability compares explicit recorded dependencies; it cannot discover undeclared physical coupling. Neither dependency matching nor a scalar agreement establishes calibration, uncertainty, physical representativeness, a validated whole vehicle, launch authorization or mission success. Source declarations do not authenticate hardware testing. Digests are unsigned local integrity references.

New investigations capture only the selected row and the model/criterion records needed to interpret it, with an exact comparison/row citation. They do not send the entire CSV, unrelated rows or complete orbital trajectories as selected-test context. Saved investigations show an app-rendered frozen evidence card independently of model prose; later comparisons never attach themselves to an old investigation. No extra tool turn is added. Existing six-request and per-job/cumulative reservation limits are preserved.

The selected-test Assistant context and explanation checks are validated offline in this milestone. The earlier live Super comparison does not prove live performance for this new payload. No live test or new provider/model selection is performed here. Explanation checks remain limited heuristics and can miss mistakes or flag acceptable wording.

## Implementation

`GET /api/test-evidence` reads a saved projection; `POST /api/test-evidence/impact` compares a supplied draft with its selected base revision without saving or calculating; `GET /api/engineering-review-export` reads the combined snapshot. Each backend projection/export uses one explicit SQLite read snapshot, verifies saved comparison integrity, and checks source stability. Investigation requests add only `test_comparison_id` and `test_row_number`; the server builds and validates the frozen bundle from its own records. No new database table or inference budget/configuration is introduced.
