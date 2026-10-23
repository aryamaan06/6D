# Numerical accuracy delivery evidence

October 23, 2026 · local build `a6215d46280d` · http://127.0.0.1:8768/

## Measured state errors

The following are maximum Euclidean position errors across every stored sample
against a separately implemented analytic elliptic Kepler reference. All inputs
are constructed ideal two-body cases. Rows compare the same duration and step
count; they are not flight measurements or universal accuracy promises.

| Constructed case | Steps | Prior Velocity Verlet error (m) | RK4 error (m) |
| --- | ---: | ---: | ---: |
| Circular, one period | 1,024 | 576.731600 | 0.001509007 |
| Circular, eight periods | 4,096 | 17,759.605994 | 0.285424874 |
| Eccentric, four periods | 4,096 | 10,649.093023 | 0.060591891 |
| Eccentric, one period | 4,096 | 6,428.775037 | 0.013709697 |
| Retrograde eccentric partial orbit | 4,096 | 26.988263 | 0.000004890 |
| High-eccentricity pericenter passage | 2,048 | 99.042583 | 0.000119204 |
| Eccentric fractional endpoint | 2,048 | 132.451570 | 0.000091381 |

The eight-period circular case at 16,384 steps measured 0.000810364 m maximum
position error. Its three-grid observed orders were approximately 4.29176 and
4.29172 for position and velocity; it supported the constructed criteria of
1 m and 0.01 m/s. Those criteria are benchmark choices, not mission requirements.

NASA NAIF CSPICE `conics`, through SpiceyPy 8.3.0/CSPICE N0067, independently
cross-checked all stored states in these eight new-solver cases. Each stayed
below the declared benchmark thresholds of 0.5 m and 0.001 m/s. The analytic
reference and CSPICE agreed within 0.00001 m and 0.00000001 m/s. CSPICE supplies
conic states independently of the application's force/integration code.
[NAIF conics documentation](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/conics_c.html).

Reference accuracy and the application's grid assessment are distinct: five of
the first seven benchmark configurations remain `not_assessed` under the app's
grid policy. Small measured error alone does not override an unavailable coarse
grid or inconclusive measured order. The full reasons appear in the JSON.

Raw records: [prior baseline](NUMERICAL_BASELINE_RESULTS.json) and
[new analytic/CSPICE results](NUMERICAL_REFERENCE_RESULTS.json). The latter binds
solver SHA-256 `33eed3ef2736155cbd9288cd63ff6126b88cab2cac15e16112b48cab0a61a03e`.
The baseline was captured before replacement; its source identity is retained.

## Verification

- **263 affected regression tests passed**, with zero failures, errors or skips:
  orbit calculations and accuracy policy, lifecycle/history, investigations,
  playback, HTTP integration, powered flight, scenarios, scalar chains, test
  evidence and historical published benchmarks.
- **Three additional history tests passed**: legacy second-order findings reopen
  unchanged without integration; a 513-step fractional endpoint is exact; a
  16,384-step eight-period saved trajectory reopens without integration.
- **Eight external-reference cases passed** as described above. The analytic
  implementation is project-authored; CSPICE is the separate external tool.
  This is not an independent human engineering review.
- **Six isolated browser workflow groups passed**: actual RK4 calculation,
  displayed method/policy, playback/export equivalence, report equivalence,
  strict-tolerance unresolved findings and preservation of the preceding run.
- **Six read-only delivered-app checks passed**: current build/runtime, retained
  review, declared template criteria, new resolution ceiling, reference preview
  and unchanged evidence with no browser errors/writes/external requests.
- Node syntax and Git whitespace checks passed. The browser screenshot was
  visually inspected; broad UI refinement is outside this milestone.

Reproduction: run `python -m unittest discover -s tests -p test_simulation.py`
and the `test_orbital_independent_reference.py`, `test_flight_event_accuracy.py`
and `test_numerical_history.py` modules similarly. Full affected module names are
retained locally in `work/numerical-regression.json`. For the external benchmark,
install development-only `spiceypy==8.3.0` into `.local/benchmark-deps` using a
compatible Python, then run
`python tools/numerical_accuracy_benchmarks.py docs/NUMERICAL_REFERENCE_RESULTS.json`.
The delivered benchmark used Python 3.12; the application uses its installed 3.14
environment. No external reference package is required to run 6D.

## Preservation and remaining scope

Before/after logical-row hashes match for every existing workspace and budget
table; provider/Assistant configurations also match. All **13 saved runs and two
investigations** are unchanged. Test projects used disposable storage. Source
changes can make a prior review historical; this is not deletion or automatic
recalculation.

No paid AI calls occurred. The existing USD 29.50 cumulative allowance and USD
2.30350988 reservations are unchanged; reservations are not billed charges.
No models were activated, credentials changed or code pushed to GitHub.

This completes the numerical-accuracy milestone within its declared scope.
Specialist time-history imports, broader operating-envelope studies and the
connected-review refinement remain separate proposed milestones. No complete
rocket physics, continuous-time extrema, flight validation or guaranteed
mission success is established. See [user guide and limitations](NUMERICAL_ACCURACY.md).
