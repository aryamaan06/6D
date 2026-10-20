# Evidence-linked Assistant

October 20, 2026. This increment improves the saved-requirement Assistant; it
does not add physics models or alter canonical findings.

## Using the result

1. Open the local workspace, select a requirement and open **Assistant**.
2. Open a saved investigation. **Recorded numerical evidence** lists the selected
   criterion, model metrics and inputs, orbital grid differences where present,
   and quantities from an explicitly selected frozen test row.
3. Choose **Open captured source**. The dialog shows the exact saved value,
   project/revision/run/review identity, JSON pointer, context and source digest.
   It opens the captured record even after the current design changes.
4. Read **Recommended next checks** and **Information to obtain or verify**. These
   are grounded review guidance, not new calculations or automatic design edits.
5. In a new AI explanation, numerical references render their complete saved
   label, value and unit. A grid difference carries its grid pair with it.
   Choose a reference to inspect the same captured source.

Saved investigations need no key to inspect. Historical model text and failed
receipts are preserved. For older investigations, the current app projects a
fact table from their captured records and labels that origin; it never replaces
missing history with a current review. Old prose does not acquire new semantic
approval or a rewritten score.

The earliest payloads omit their run ID. Their labelled projection uses the run
identity preserved on the original investigation receipt while checking the
captured project/revision/review binding. Explicit conflicting run IDs remain
rejected, and every new-policy payload must carry its matching run ID.

## New explanation contract

New receipts record `evidence_facts_prose_policy=evidence_links_v1`. The provider
uses `[[fact:ID]]` for numerical details instead of retyping values, grid counts
or revision numbers. A concise explanation without numerical claims is allowed;
the deterministic table remains available. The exact product name 6D is a label,
not an engineering quantity.

The application derives the fact catalog from captured requirement/model
evidence, never from a model-supplied catalog. Each fact identity binds the scope,
escaped JSON pointer, captured-source digest, value, unit and context. Acceptance
rederives the catalog and rejects mismatches, unknown references and numerical
literals outside those references. No new provider schema keywords, retry,
format truncation or budget increase is needed.

The catalog is bounded to 160 entries. Its declared coverage includes selected
criterion comparisons, model metrics/inputs, orbital grid criteria/differences,
same-adapter reproduction and frozen test quantities. It excludes full time
histories, other diagnostics and prior-revision values, which remain in captured
JSON. The compact wire projection carries labels and values while full source
pointers and digests remain saved locally.

This binds a reference to its source. It does not establish that the source is
physically valid, that surrounding prose makes the right inference, or that
written-out numerical claims are correct. Existing limited status/wording/test
checks remain in force. `semantic_accuracy_established` remains false.

## Identical-evidence comparison

The separate **Evidence-linked Assistant comparison** in **Connect AI** records
the new batch without changing historical evaluations or model selection. Its
fixed three cases are orbital grid evidence, a changed thermal requirement limit
with unchanged physical inputs, and unsupported control coverage. Nano, Super
and Ultra receive identical snapshots for each case.

Preparation uses offline synthetic transports. It does not establish model
performance. A deliberate live start requires a private connection and the fixed
USD 2 ceiling, at most 54 reservations in the existing USD 29.50 allowance. Each
case retains the existing six-request and Nano .10/Super .20/Ultra .35 ceilings.
No automatic retry, fallback or model activation occurs.

Workflow completion, absence of detected fact-contract violations, and actual
use of fact links have separate counts. Generic prose can observe the contract
without using a numerical reference. None of these counts is independent human
engineering validation. Failed/skipped cases, raw receipts, reservations and
latency remain inspectable. Reservations are not billed cost.

Partner tracing and review services can be connected after activation. They are
not required to inspect the application or run these local checks.
