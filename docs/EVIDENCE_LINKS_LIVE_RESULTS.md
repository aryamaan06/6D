# Evidence-linked Assistant live comparison

October 20, 2026. Arya explicitly connected privately and authorized one batch
within the USD 2 ceiling. Comparison `566a4f53acab47e5b6d8fce6bb7068f7` is preserved
in its own table and raw artifact. No retry or activation followed it.

## Result

The batch runner finished, but **no candidate completed the new explanation
contract**. Each candidate reached the final explanation on the same first
orbital case after reading the requirement/model and reproducing the saved
calculation. Each rejected explanation stopped that candidate, leaving its two
remaining cases untested. “Completed” on the batch denotes a finished harness,
not successful candidate investigations.

| Candidate | Attempted / planned | Accepted explanations | Untested | Reservations | Live case time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nano | 1 / 3 | 0 | 2 | USD .00950604 | 17.57 s |
| Super | 1 / 3 | 0 | 2 | USD .04506780 | 14.99 s |
| Ultra | 1 / 3 | 0 | 2 | USD .15022600 | 13.63 s |

One case per candidate cannot establish a general quality, latency or
cost-efficiency ranking. These are conservative reservations and single observed
wall-clock times, not verified billed charges or a representative benchmark.

## What actually failed

**Nano and Super copied the correct saved metric and limit.** Both reported the
maximum sampled radius as 7,000,032.9432812715 m against 7,100,000 m and retained
the bounded `met` finding. Their immediate rejection was the new contract:
numerical details were typed as prose instead of exact application-rendered fact
references. This is real format noncompliance; it is not evidence that those two
numbers were fabricated or that their comparison was reversed. Nano omitted the
requested grid-pair explanation; Super's description of grid agreement and
reproducibility also needs clearer separation.

**Ultra attempted fact references but made a semantic source-selection error.**
It placed `[[fact:f96828357bf4fbd952aecf8fc]]` after the claimed declared limit of
7,100,000 m. That fact actually records `final_radius_m`,
7,000,000.000000004 m. The correct declared-limit facts are separate. A token's
membership in the catalog does not establish that surrounding prose used the
right engineering role.

Ultra also retyped quantities and grouped six input references in an unsupported
syntax. The check's `unknown_fact_reference` reason includes malformed syntax:
the grouped IDs are known, rather than six fabricated identifiers. Its diagnostic
numeric-literal list includes digits in malformed tokens and unit exponents as
well as actual unbound values. It is not a count of independent false numerical
claims. The explicit radius/limit/input/grid quantities alone were sufficient to
violate the policy.

Ultra's finer-grid differences were correctly labelled this time:
1024→2048, 432.547248450107 m and .4462626079471538 m/s. Its scope caveats and
recommendation to review input provenance and obtain independent analysis were
useful. That improvement does not erase the wrong limit reference or qualify the
six untested candidate-case combinations.

## Separate review and limits

An independently delegated Codex AI review checked all 75 captured facts against
their pointers, source digests and scope-bound identities. Those checks passed.
It inspected the rejected summaries separately from automated workflow scores.
This is another AI review, **not independent human aerospace validation**.

The source table and captured-source links work, and the new guard retained the
unacceptable explanations instead of silently promoting them. **Live acceptance
of the new explanation contract remains unresolved.** All three deterministic
same-adapter rechecks reproduced their saved result; that proves reproducibility
only, not physical validity.

Super remains selected under the earlier qualifying comparison. The global Nano
configuration is unchanged. This new batch does not establish compliance of
Super or any other candidate with the new reference-format contract.

## Next proposed correction

Keep the rejected receipts and replay these actual outputs offline. Simplify the
final response contract, put short examples next to the final action, and test
valid references used in the wrong metric/limit/grid role. For a stronger numeric
binding guarantee, use typed roles resolved/rendered by the application rather
than relying on free prose to select and describe opaque fact IDs. Repeating the
same paid batch without that work is not justified. No new paid run is authorized
or queued by this report.

## Accounting and preservation

The batch made **12 reservations / 12 native action responses**, reserving
**USD .20479984**, below USD 2. The three final explanations remain rejected.
Cumulative reservations are **USD 1.8085918 of USD 29.50**, leaving
**USD 27.6914082** in local reservation capacity. These values do not verify the
provider wallet balance or billed usage.

All original table rows and configuration hashes match the build baseline. One
new completed batch record was added separately; old scores, failures and model
selection were not rewritten. No server restart or application source change was
made during this live comparison. The private connection remains in server
memory and is not exported.

Refresh http://127.0.0.1:8768/ (build `207b0fc5ba9e`) and open **Connect AI →
Evidence-linked explanation comparison** for the counts, stopped-case reasons
and raw download. The report distinguishes contract passes and actual fact-link
use from workflow completion and semantic correctness.

Five final read-only browser checks passed against the actual saved results:
three candidate rows each show zero accepted investigations and two untested
cases, the separate fact-link column is present, the export is available and
model/reservation totals are unchanged by inspection. No new inference request
or application-source change was made during this verification.

Retained evidence:

- `artifacts/evidence-links/566a4f53acab47e5b6d8fce6bb7068f7.json`: immutable raw batch.
- `work/evidence-links-independent-review.json`: separate Codex AI semantic review.
- `work/evidence-links-live-result.json`: saved status, raw hash and reservation totals.
- `work/evidence-links-live-preservation.json`: original-row/configuration and accounting checks.
- `work/evidence-links-live-browser.json`: actual read-only result-display checks.
