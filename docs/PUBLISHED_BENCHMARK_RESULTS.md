# Published engineering reference benchmarks — October 19, 2026

All **30 declared checks passed** after a narrow orbital input-boundary fix. Seven of seven maintained model types have recorded numerical reference evidence. This is bounded implementation verification; it is not general physical validation or launch readiness.

**Material accuracy finding:** the fixed-grid orbital solver differs from the external two-body reference by **17.76 km over eight circular periods**, 14.56 km over 7.5 periods, 8.38 km over four moderately eccentric periods and 6.43 km over one more-eccentric period at 4096 steps. These comparisons pass broad, predeclared software regression gates. Those gates do **not** establish acceptable error for a mission criterion. An explicit engineering accuracy budget is still needed when using such results.

## What was compared

| Maintained model | Total checks | Numerical/reference checks | Domain gates |
| --- | ---: | ---: | ---: |
| attitude_control | 6 | 5 | 1 |
| drag_load | 3 | 2 | 1 |
| ideal_propulsion | 4 | 3 | 1 |
| orbital_trajectory | 9 | 7 | 2 |
| power_energy_budget | 4 | 3 | 1 |
| radiative_equilibrium | 2 | 1 | 1 |
| static_cantilever | 2 | 1 | 1 |

The suite contains six published worked-example checks (two of them deliberately coarse NASA rounded examples), six external-software/refinement comparisons, ten constructed analytical/equation checks and eight domain gates. Constructed inputs are identified individually; a mathematical source citation is never presented as measured spacecraft data or an externally published numerical design.

- **Propulsion:** NASA ideal rocket and specific-impulse relations; a coarse published mass-ratio example plus independent 60-digit arithmetic for constructed cases.
- **Cantilever:** MIT stress and free-end-deflection derivations, evaluated independently with supplied constructed geometry/load. There is no matching published numerical geometry claimed.
- **Thermal:** NASA radiator exchange with view factor one and modern NIST constants. Independent high-precision arithmetic checks a constructed finite-background equilibrium; no thermal hardware validation is implied.
- **Drag:** NASA drag convention and a rounded Smeaton worked illustration, plus a strict independently evaluated constructed case.
- **Power:** externally stated OpenStax Example 9.10 energy totals converted to SI; an independently summed two-mode schedule distinguishes energy sufficiency from inadequate battery power.
- **Control:** two MIT published damped-oscillator solutions mapped to the rigid-axis PD equations, plus independently solved overdamped, constant-disturbance and continuously clipped-torque cases. Every saved sample, signed error and command/applied torque is compared.
- **Orbit:** independently maintained NASA NAIF CSPICE_N0067 `prop2b`/`conics` through development-only SpiceyPy 8.3.0. Each propagation compares all 4097 saved states. Circular and eccentric refinement studies additionally compare 1024/2048/4096-step grids. No production force, integration or element-extraction helper supplies the expected trajectories.

## Orbital results and tolerance interpretation

| Constructed reference case | Maximum position difference (m) |
| --- | ---: |
| orbit_spice_circular_eight_periods | 17759.606 |
| orbit_spice_circular_seven_and_half_periods | 14560.564 |
| orbit_spice_inclined_eccentric_four_periods | 8382.917 |
| orbit_spice_eccentric_one_period | 6428.775 |
| orbit_spice_retrograde_eccentric | 45.097 |

State regression limits were declared before running: maximum position difference divided by semi-major axis and velocity difference divided by circular speed <= 2%; sampled scalar metrics <= 1% relative difference. They are broad defect-detection levels, not engineering requirements. Circular one-period fine-grid checks additionally require <= 1e-5 normalized state difference, and the two refinement studies require measured order between 1.8 and 2.2. Actual checkpoint states, five sampled metrics, relative errors and refinement records remain in the JSON receipt.

The circular/eccentric comparisons show approximately second-order refinement for these cases. Conservation diagnostics alone would miss accumulated phase error. This milestone retains the fixed-grid solver and documents the resulting limits rather than claiming those errors are universally acceptable.

## Defect found and fixed

The externally constructed exact eight-period case was rejected before numerical comparison: requested duration 46628.13310148812 s versus a reconstructed bound 46628.133101488085 s, a five-ULP difference. `simulation._orbit` now permits only a 16-ULP roundoff allowance at this numerical window boundary. This is not a mission-duration engineering tolerance. Meaningful excesses, including nine-period requests and a 32-ULP excess, remain rejected by focused tests. The original failing receipt remains in `artifacts/published-benchmarks/pre-fix-orbit-boundary.json`.

The NASA Smeaton worked illustration also has a printed-value rounding discrepancy: the nominal printed density/coefficient gives 0.003262805333 rather than the printed 0.00327. The receipt preserves the failed output-rounding-only diagnostic and an explicitly assumed input-print rounding contribution. The coarse combined allowance is 1.2e-5; a separate strict Decimal drag comparison passes. This is source precision handling, not a production bug or an assertion of physical measurement uncertainty.

## Validation, provenance and reproduction

The full regression suite passed **765 tests** in 183.832 s, including eight new benchmark/boundary tests. A deliberate cantilever-calculator fault is detected by the independent reference; a missing external dependency produces a controlled failed benchmark with missing-model disclosure and no substitute oracle.

The complete finite JSON receipt is `artifacts/published-benchmarks/summary.json`, digest `4ab06e50400664103cc9e16d6de531d72a06341c7b5d32d8409ddb86441e8131`. It includes every source URL, supplied input, expected/actual output, tolerance, error/check result, case classification, source fingerprints, runtime information and limitations. Program/fixture hashes were unchanged during the run. Benchmark elapsed time was 1.337 s; this is not a customer application performance measurement.

From the repository folder:

```powershell
python -m pip install --target .local/benchmark-deps --only-binary=:all: -r requirements-benchmarks.txt
python tools/benchmark_engineering.py
```

The pin is development-only. The application needs neither SpiceyPy nor access to the reference toolkit. Sources are not downloaded at benchmark execution. No keys, paid inference or production database writes are used by the runner.

Detailed source mappings: [static references](PUBLISHED_STATIC_REFERENCES.md), [power](PUBLISHED_POWER_REFERENCES.md), [control](PUBLISHED_CONTROL_REFERENCES.md), [orbit](PUBLISHED_ORBIT_REFERENCES.md). [Applicability audit](MODEL_APPLICABILITY_AUDIT.md) distinguishes enforced gates from assumptions current inputs cannot establish. [Acceptance protocol](PUBLISHED_BENCHMARK_PROTOCOL.md) records the comparison scope.

## Remaining gaps

Reference mapping, source transcription, expected-value code and tolerance selection were assembled by AI; independent human engineering review remains needed. Finite examples do not establish real-vehicle geometry, loads, coefficients, environments, hardware performance or uncertainties. General control clipping/release transitions remain externally unbenchmarked. Orbital mission accuracy, between-sample constraint assurance, broader physics, live AI explanation quality and customer usefulness are not established by this suite.

Local app delivery: http://127.0.0.1:8768/, build **854446b6f9d8**, runtime `e360e007395148d75ea070203242dcea1e60565d40fb7e6b3b70ef49315ce24c`. This milestone supplies reference evidence/reporting and the roundoff fix; model count remains seven. Founder data/provider/allowance preservation is recorded in `work/benchmarks-preservation.json`. Paid Nebius calls: **zero**.

## Case index

| Case | Reference classification | Result |
| --- | --- | --- |
| propulsion_nasa_rounded_worked_example | published_rounded_worked_example | Pass |
| propulsion_general | published_equation_constructed_case | Pass |
| propulsion_zero_delta_v | published_equation_constructed_case | Pass |
| propulsion_negative_delta_v | domain_guard_not_physical_validation | Pass |
| cantilever_tip_load | published_equation_constructed_case | Pass |
| radiation_finite_background | published_equation_constructed_case | Pass |
| radiation_emissivity_above_one | domain_guard_not_physical_validation | Pass |
| drag_nasa_smeaton_worked_example | published_rounded_worked_example | Pass |
| drag_general | published_equation_constructed_case | Pass |
| drag_negative_speed_magnitude | domain_guard_not_physical_validation | Pass |
| power-openstax-9-10-incandescent | published_worked_example | Pass |
| power-openstax-9-10-led | published_worked_example | Pass |
| power-piecewise-independent-budget | reference_equation_constructed | Pass |
| control_mit_worked_underdamped | published_worked_solution | Pass |
| control_mit_worked_critical | published_worked_solution | Pass |
| control_constructed_overdamped | constructed_from_published_equation | Pass |
| control_constructed_constant_disturbance | constructed_from_published_equation | Pass |
| control_constructed_constant_clipped_torque | constructed_from_published_equation | Pass |
| orbit_spice_circular_eight_periods | independent_external_software_CSPICE_universal_variables | Pass |
| orbit_spice_circular_seven_and_half_periods | independent_external_software_CSPICE_universal_variables | Pass |
| orbit_spice_inclined_eccentric_four_periods | independent_external_software_CSPICE_universal_variables | Pass |
| orbit_spice_eccentric_one_period | independent_external_software_CSPICE_universal_variables | Pass |
| orbit_spice_retrograde_eccentric | independent_external_software_CSPICE_universal_variables | Pass |
| orbit_circular_analytic_refinement | published_circular_solution_analytic_refinement | Pass |
| orbit_spice_eccentric_refinement | independent_external_software_refinement | Pass |
| guard_beam_zero_length | domain_guard_not_physical_validation | Pass |
| guard_power_fractional_equipment_count | domain_guard_not_physical_validation | Pass |
| guard_control_underresolved_grid | domain_guard_not_physical_validation | Pass |
| guard_orbit_negative_gravitational_parameter | domain_guard_not_physical_validation | Pass |
| guard_orbit_nine_periods | domain_guard_not_physical_validation | Pass |
