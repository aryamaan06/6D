# Orbital numerical accuracy receipt

The orbital project adapter can now retain three fixed-resolution trajectories
and compare their signed position and velocity vectors at every aligned stored
time. This assesses explicit numerical accuracy criteria for the supplied
two-body calculation. It does not validate the physical model or establish a
rigorous bound on the unknown true trajectory error.

The existing `evaluate(parameters) -> (metrics, artifact)` and v1 artifact
validator remain unchanged. Historical receipts are not rewritten or recalculated.
The additional entry point is:

```python
evaluate_with_accuracy(parameters, criteria=None)
# -> (sampled_metrics, finest_orbit_artifact, numerical_accuracy_receipt)
```

Criteria are optional metadata with exactly these fields and no inferred values:

```json
{
  "position_tolerance_m": 1.0,
  "velocity_tolerance_m_s": 0.001,
  "source": "The engineer's stated accuracy requirement and its source"
}
```

Both tolerances must be positive finite numbers; booleans, zero, negative values,
nonfinite values and unknown fields are rejected. The source must be nonempty
text. These example values are constructed test criteria, not a recommendation
or a mission accuracy requirement.

## Calculation and statuses

The existing `steps` value is the finest resolution. The adapter first preserves
that result, then attempts `steps / 4` and `steps / 2`, without increasing the
existing 4096-step work limit or weakening any physical/numerical domain guard.
The finest count must be divisible by four and at least 64 so all three grids
respect the existing 16-step minimum.

For each factor-of-two comparison, every coarse-grid sample is aligned with the
corresponding even-index fine-grid sample. Position and velocity differences are
Euclidean norms of signed vector differences. This catches phase errors that
equal radii, speeds, energy or final-state-only comparisons would miss. No
interpolation or between-sample accuracy claim is introduced.

For each observable, the measured order is:

```text
p = log2(maximum coarse/middle vector difference)
    - log2(maximum middle/fine vector difference)
```

The receipt uses the following states:

| Status | Required evidence |
| --- | --- |
| `supported` | Position and velocity orders both lie within 1.8–2.2, and each worst middle/fine difference is no larger than its supplied tolerance. |
| `insufficient_accuracy` | Complete grids show order outside 1.8–2.2 or a middle/fine difference above its supplied tolerance. |
| `not_assessed` | Criteria are missing, the grid cannot support three levels, a coarser grid is rejected, or zero differences prevent a measurable refinement order. |

The accepted order interval is a declared numerical diagnostic policy around
the solver's second-order method. Observed order plus small grid differences do
not make those differences a proven true-error bound. Neither energy nor angular
momentum conservation contributes to the accuracy verdict.

If a coarser run is rejected, the valid finest trajectory and its metrics remain
available, but numerical accuracy is unresolved. A one-period 1024-step circular
case, for example, cannot use a 256-step coarse reference under the existing
pericenter-step guard; a 2048-step finest grid can support that reference sequence.
An eight-period 4096-step case cannot establish this three-grid assessment within
the current limits. Its result must not acquire an accuracy pass from the broad
published-reference regression threshold or from conservation diagnostics.

## Retained structure and consistency validation

The additional receipt schema is `sixd.orbit-accuracy.v1`. Its fields are:

| Field | Meaning |
| --- | --- |
| `status`, `reason` | Reconstructed assessment state and explicit reason. |
| `criteria` | The canonical explicit criteria, or `null` when none were supplied. |
| `method` | Three-grid method, expected order, accepted interval and `error_bound_claimed: false`. |
| `reference_levels` | Up to two entries `{steps, artifact}` containing full immutable coarse and middle v1 artifacts. The finest artifact is retained separately in the existing model result. |
| `reference_failure` | `null`, or `{steps, message}` identifying the first rejected coarser calculation. |
| `comparisons` | The two step counts, aligned sample count, maximum position difference in metres and maximum velocity difference in metres per second for each adjacent grid pair. |
| `observed_orders` | Separate position and velocity orders, or `null` if not measurable. |
| `limitations` | Fixed explicit scope and numerical-evidence limitations. |

`validate_accuracy(accuracy, finest_artifact, parameters, criteria,
source_fingerprint)` returns `True` or raises. It validates all retained v1
artifacts against their own bound grid and the retained solver source, recomputes
the difference norms, orders and verdict, and checks exact finite JSON
consistency. It never invokes propagation or reapplies today's solver-domain
policy to saved historical evidence.

Altered verdicts, criteria, differences, orders, grid identity, sample/vector
consistency, limitations or retained source identity fail this consistency
check. These local receipts and digests are unsigned: arithmetic consistency
does not authenticate an external experiment or prevent a party from forging a
fully self-consistent replacement record.

## Verification

`tests/test_orbital_accuracy.py` contains 13 focused tests covering:

- Missing/invalid criteria and separate position/velocity tolerance failures.
- A constructed circular analytic reference showing nonzero phase error despite
  tiny energy drift.
- Signed intermediate-state reversal with unchanged scalar radius/speed.
- An injected first-order phase defect that fails despite loose tolerances.
- Coarser-grid rejection, unsupported refinement grids and preserved finest data.
- Receipt tampering and validation with propagation/current-domain calls blocked.
- Unchanged legacy artifact structure and validation.

Published external comparisons and their independently observed limitations
remain in [PUBLISHED_BENCHMARK_RESULTS.md](PUBLISHED_BENCHMARK_RESULTS.md).
No external dependency or paid inference is required for these accuracy receipts.

## Playback projection

Project-bound playback includes a compact copy of the saved numerical accuracy
receipt and model applicability context. Full coarse/middle artifacts remain in
the identified canonical project review; playback does not duplicate them or
perform a new calculation. Listing summaries and exported playback JSON retain
the same declared criteria, differences, orders, reason and limitations.

The playback screen distinguishes supported refinement criteria, insufficient
accuracy, unassessed accuracy and historical reviews that predate this evidence.
It shows physical applicability as unassessed and lists the external evidence
still required. Exploratory scenarios retain their original separate receipts
and explicitly have no project accuracy assessment. Historical wrappers lacking
new metadata are not rewritten or assigned an invented pass.

`tests/test_accuracy_playback.py` adds five focused checks for compact/exported
projection, immutable canonical evidence, listing context, legacy history,
standalone isolation and the actual JavaScript accuracy-section renderer.
