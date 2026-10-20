# Ultra compatibility investigation

October 20, 2026. The historical thirty-task comparison and its failed Ultra record are preserved.

## Precise finding

Targeted diagnostic `c0ae01d07c904b2e9673014bac23ce1d` made four request reservations and accepted the first three read/recheck responses. Its fourth response was a native selector envelope but the finish summary contained **2611 characters**, exceeding the then-current **2400-character** local formatting bound. The new controlled diagnostic retained `selection_rejection=summary_length` and `summary_characters=2611` without storing rejected text or credentials.

The response used 644 completion tokens, with no reasoning tokens, against the unchanged 2048-token output ceiling. It was not reported as truncated. This establishes the cause of this new run's rejection, not the exact cause or semantic quality of the old unretained response.

The failure reserved **USD .136268**. It remains failed; no output was truncated or retroactively accepted. Before this milestone, cumulative reservations were USD 1.33125596; after this diagnostic they were USD 1.46752396 of the existing USD 29.50 allowance. These are conservative reservations, not billed charges or a verified provider wallet balance.

## Implemented corrections

- Adapter errors now distinguish malformed JSON, wrong selection shape/action, citation shape/mismatch, summary type/length, nonempty read payload and invalid envelope/count/arguments. Only allowlisted reasons and bounded counts survive. Unknown text/fields and credentials do not.
- `ProviderError` is no longer swallowed by the generic JSON-error handler, and the provider merges controlled rejection details with envelope/usage diagnostics instead of replacing them.
- The first live diagnostic showed that descriptions requesting brevity did not prevent an overlong response. The application formatting contract now permits **4000 characters**, retaining the **8192-character raw action JSON bound**, **2048 output-token ceiling**, exact citations/actions/types, private-key rejection and all explanation/evidence checks. Request descriptions and local validation use one shared constant. No engineering requirement or canonical finding changes.
- No explanation text is automatically shortened. Even an in-bound explanation must pass the normal evidence checks, which do not establish complete semantic correctness.
- The targeted diagnostic has its own table, status/export and read-only Connect AI panel. It never replaces historical comparison evidence or enables Ultra. New records capture the character contract and application source hashes.

The engineering criteria and response-formatting contract are separate. The larger formatting allowance is not evidence that Ultra is more accurate. It simply removes the particular short-output mismatch observed here while keeping bounded processing.

## Offline verification

The initial focused regression passed **215 tests** across provider/action/quality, diagnostic service/API, historical selection and workspace/evaluation boundaries. After the evidence-driven formatting revision, **95 affected tests passed**, covering the 4000-character boundary, 4001-character rejection, empty/invalid summaries, citations, action handling, credential redaction, numerical-contradiction rejection and preserved model selection. Counts overlap; they are not 310 distinct tests. JavaScript syntax and six initial read-only browser checks passed. Original user rows, historical evaluations and account/model-selection files are unchanged; the new diagnostic and ledger reservations are separate.

## Corrected live verification — October 20

Arya explicitly authorized one fresh corrected case under the USD .35/six-request task ceiling. Run `18c796f6f5e74e918c3e4e3e37d11a51` made four request reservations and accepted four native action responses. Its 2566-character explanation passed the revised 4000-character contract and supplied the exact required citations. This verifies the formatting correction for this case.

The live receipt remains **failed**, because the limited wording checker incorrectly flagged “it does not authorize launch or guarantee mission success” as a positive guarantee. The second coordinated denial inherited “does not”; the old checker did not recognize that narrow construction. The checker now masks only that explicit paired denial and its reversed order. Counterexamples with a later positive guarantee, contrast or separate launch claim still fail. All **97 affected offline tests passed**. This correction was made offline; no third paid run occurred and the live receipt/score was not rewritten.

Offline reassessment of the captured explanation no longer blocks on that wording. **This is not semantic approval.** Separate Codex AI review found a numerical attribution error:

| Grid pair | Recorded position difference | Recorded velocity difference |
| --- | ---: | ---: |
| 512 → 1024 | 1730.1019139093717 m | 1.784938624275503 m/s |
| 1024 → 2048 | 432.547248450107 m | .4462626079471538 m/s |

Ultra described approximately 432.5 m and .45 m/s as belonging to 512/1024. Those are the finer 1024/2048 comparison's rounded values. Its bounded `met` finding, radius/limit comparison, reproducibility distinction and denial of launch authorization otherwise agree with the captured evidence. The explanation needs revision; a clean limited wording check cannot establish correct numerical attribution.

The old unretained comparison response's exact cause remains unknown. The new diagnosis proved one formatting failure, and the new verification proved its correction while exposing both a checker false positive and a genuine explanation weakness. Neither failed receipt is retroactively converted into a live pass.

Super remains the selected project Assistant. Ultra's remaining nine original comparison cases are still untested. Independent human engineering review remains pending. No full comparison rerun, automatic retry or stronger-model activation occurred.

## Final accounting and opening

The corrected verification reserved USD .136268; the two runs together reserved **USD .272536**, below the original USD .50 milestone ceiling. Cumulative reservations are **USD 1.60379196** of USD 29.50, leaving USD 27.89620804 in local reservation capacity. Reservations are not provider billed charges or a confirmed wallet balance.

Refresh http://127.0.0.1:8768/ and confirm build **a654eda494e1**. **Connect AI → Ultra compatibility diagnostic** shows the preserved latest failed record and raw download; historical receipt states are not automatically recalculated after checker changes. This report and the separate offline-review JSON explain the later reassessment and grid-attribution issue. Original workspace rows, historical comparisons and account/model selection are preserved; only separate diagnostic records/reservations were added. Final read-only browser checks make no inference calls. The final restart cleared the memory-only connection; no reconnection is needed to inspect results or run local calculations.

## Retained evidence

- `artifacts/ultra-diagnostic/c0ae01d07c904b2e9673014bac23ce1d.json`: unchanged precise failure.
- `artifacts/ultra-diagnostic/18c796f6f5e74e918c3e4e3e37d11a51.json`: unchanged corrected live verification receipt.
- `artifacts/ultra-diagnostic/18c796f6f5e74e918c3e4e3e37d11a51-offline-review.json`: separate Codex AI reassessment, source hash and numerical-attribution finding.
- `work/ultra-regression.json` and `.log`: initial focused verification.
- `work/ultra-format-regression.log`: affected checks after the formatting revision.
- `work/ultra-final-regression.log`: 97 affected checks after the narrow coordinated-negation correction.
- `work/ultra-preservation.json`: original rows/configuration audit.
- `work/ultra-browser.json`: read-only browser acceptance and actual build identity.

The exact provider decoder version/capabilities have not been established. Research into [XGrammar's documented schema/format behavior](https://xgrammar.mlc.ai/docs/latest/structural_tag/structural_tag.html) reinforces that a tool description alone must not be represented as enforced length control. No speculative provider keyword/profile change was made to manufacture a passing run.
