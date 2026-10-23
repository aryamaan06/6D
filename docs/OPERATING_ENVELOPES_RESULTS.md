# Operating-envelope delivery evidence

October 23, 2026 · local build `395f0632f981` · http://127.0.0.1:8768/

Delivered: bounded Cartesian range preview/calculation, fixed-criterion controls,
worst observed per-requirement margins with ties, unresolved case retention,
immutable history, case inspection and same-snapshot report/JSON integration.
See the [user guide](OPERATING_ENVELOPES.md) and
[acceptance criteria](OPERATING_ENVELOPES_ACCEPTANCE.md).

## Verification

- **20 new backend tests passed**: explicit Cartesian order/endpoints, solver-free
  preview, independent arithmetic, ties, equality differences, unresolved inputs,
  overflow, criterion/numerical-setting freeze, duplicate/unsafe/collapsed grids,
  stale baseline/revision during calculation, work limits, solver-free history,
  tampering with recomputed outer digests, receipt-size/history omissions.
- **16 existing scenario tests passed**, preserving legacy behavior and scope.
- **Five new HTTP tests passed**: preview/run, exact recorded arithmetic,
  canonical-data preservation, combined snapshot equality, fixed-limit/product
  bounds, stale baseline, static assets and cross-origin refusal.
- **77 existing integration tests passed**, no failures/errors/skips, across
  calculation chains, scenario design comparisons and HTTP paths, linked-evidence
  exports and simulation imports. Results/module names are retained locally in
  `work/envelope-regression.json`.
- **Eight integrated browser groups passed**: eligible parameter choices, exact
  preview before saving, invalidated-preview refusal, worst/failing-case evidence,
  unchanged canonical review, report/export agreement, mixed violations and
  unassessed cases, and retained historical results after a baseline rerun.
- **Six isolated frontend check groups passed** for field validation, preview
  gating, escaping/unit notation, stale-preview handling, duplicate axes and
  draft guards. Browser testing additionally caught and fixed parameter selections
  being cleared while metadata loaded on returning to the page. The integrated
  workflow passed after the final fix, and its screenshot was visually inspected.
- **Six read-only delivered-app groups passed**: loaded build/runtime, truthful
  empty study context, page opening, explicit range/baseline actions, full report,
  no project writes/browser errors/external requests. Results are retained locally
  in `work/envelope-current-results.json`. Node syntax and Git whitespace checks
  also passed.

A separate coding-agent review identified numerical tolerance inputs that needed
to be frozen; that correction is included. This is not independent human
engineering validation or proof of all model assumptions.

## Constructed arithmetic check

The four-case drag example used density 0.01/0.03 kg/m³ and speed 100/200 m/s,
with coefficient 1, area 1 m² and fixed limit 100 N. Independently applying
`0.5 × density × speed² × coefficient × area` gives 50, 200, 150 and 600 N.
The study retained one met and three unmet cases, with worst margin **−500 N**
at the fourth combination. A second grid including negative density retained
the two invalid-input cases as unassessed alongside observed violations.
These checks establish software behavior for constructed values, not flight data
or an externally validated operating envelope.

Reproduce new tests with
`python -m unittest discover -s tests -p test_operating_envelopes.py` and
`python -m unittest discover -s tests -p test_envelopes_api.py`.

## Preservation and remaining work

The pre-milestone workspace contained **two projects, two revisions, thirteen runs
and two investigations**; the second project already existed when this build
started and was retained. Logical row hashes for every workspace/budget table
and provider/Assistant configuration match that captured baseline. No founder
project fixtures, studies, recalculations or migrations were added. All test
studies used disposable storage.

No paid calls, model activation, provider connections, GitHub push or deployment
occurred. The existing USD29.50 allowance and USD2.30350988 reservations remain
unchanged; reservations are not billed charges.

Two of the agreed five builds are now delivered. Three remain: connected review
and interface polish, live AI integration/evaluation, final corrections/deployment/
submission demonstration. Those remain separate authorizations. This milestone
does not establish continuous safe bounds, complete rocket physics or a score.
