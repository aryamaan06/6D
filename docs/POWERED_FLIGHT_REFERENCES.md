# Powered vertical-flight references

Checked October 22, 2026. Inputs in the reference cases are constructed; none is
flight data. A separate numerical tool improves cross-checking but does not
provide an independent human engineering review.

## Equations and scope

The maintained model integrates height and vertical velocity from rest:

    dh/dt = v
    dv/dt = (T - 0.5*rho*Cd*A*v*abs(v))/m - mu/(R+h)^2
    rho = rho0*exp(-h/H)
    mdot = T/(Isp*g0), g0 = 9.80665 m/s²

Mass is `m0-mdot*t` through burnout, then exactly the supplied dry mass. Thrust
is constant before burnout and zero during coast. The atmosphere is stationary;
height is measured from the supplied reference radius. Standard gravity converts
Isp to effective exhaust velocity; it is not the modeled local gravity.

- [NASA ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/)
  supplies the ideal constant-effective-exhaust-velocity relation. Our vacuum
  test checks `v=ve*ln(m0/m)` and its independently integrated height expression
  `h=ve*(t-(m/mdot)*ln(m0/m))`, followed by constant-velocity coast.
- [NASA specific impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/)
  describes the thrust/mass-flow/Isp relation.
- [NASA drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/)
  supplies the force-magnitude relation and coefficient/reference-area convention.
  The signed vertical specialization opposes velocity in ascent and descent.
- [NASA-hosted atmospheric-entry paper, exponential atmosphere equation 14](https://ntrs.nasa.gov/api/citations/20250004773/downloads/2025AIAA_Adaptive_Neural_Net_Atmos_Entry_Guidance.pdf)
  describes a reference-density/scale-height exponential approximation. This app
  does not implement a standard atmosphere, GRAM, weather or aeroheating.
- [SciPy solve_ivp documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
  documents the adaptive eighth-order DOP853 method used for the cross-check.

## Separate-tool check

`tests/test_powered_flight_reference.py` independently writes the force equations
and integrates three states (height, velocity, mass), using SciPy DOP853, relative
tolerance `2e-12`, absolute tolerance `1e-10`, and maximum step one eightieth of
each segment. It uses no production RHS or grid-integration helper. The app uses
fixed-step RK4 and analytical mass. Both methods share the declared idealized
physical assumptions, so agreement cannot establish those assumptions' validity.

Four cases cover normal atmosphere, descending above-surface coast, a small
initial thrust margin, and a thinner atmosphere. Every retained fine-grid sample
is compared. Allowed differences: 0.0002 m in height, 0.000002 m/s in velocity,
and 0.00000001 kg in mass. Actual values and library version are recorded in
`POWERED_FLIGHT_REFERENCE_RESULTS.json`.

SciPy is test-only. To reproduce in a development environment with SciPy:

    python -m unittest discover -s tests -p test_powered_flight_reference.py -v

Without SciPy this reference suite explicitly skips; that is not a pass. The app
and its core regression tests need no SciPy dependency.

## Numerical limitations

RK4 executes n, 2n and 4n steps per segment. Both aligned grid comparisons must
meet supplied absolute-plus-relative height and velocity tolerances. Observed
metric differences and declared tolerances set displayed numerical allowances.
A requirement whose threshold overlaps that allowance remains unassessed. These
are empirical agreement policies, not rigorous bounds. Sampled maxima are not
continuous extrema, and pressure/force extrema lack separately declared physical
uncertainty. Cutoff is retained on both sides to show instantaneous thrust loss.

The computational domain is above the reference surface, height at most 1e7 m,
speed magnitude at most 1e5 m/s, total time at most 10000 s, and coarse grid
8..512 steps per segment. These bounds control computation; they do not certify
physical applicability within the range. Surface crossing rejects this model
run; it does not simulate impact or landing.

History checks validate input/source binding, sample times, mass and forces,
metrics, events and diagnostics from retained grids without reintegrating. A
deliberately forged, self-consistent trajectory is not prevented by unsigned
digests. No authenticity or universal trajectory-correctness claim is made.
