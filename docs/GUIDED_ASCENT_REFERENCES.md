# Planar ascent: equations, assumptions and numerical references

Checked October 24, 2026. `guided_ascent` is a separate bounded adapter; the existing one-dimensional `powered_flight` model remains available. It calculates the consequences of a supplied steering programme, not a controller's ability to follow it.

## Coordinate and force convention

Position **r** = (x,y) and velocity **v** are expressed in a nonrotating body-centered inertial plane. Initial position is (R,0), initially at rest; R is the supplied launch radius. Define r = |**r**|, outward radial **e**r = **r**/r and positive counterclockwise tangent **e**t = (−y/r,x/r). Altitude is r−R. Signed downrange is R atan2(y,x), a surface arc; it is not Cartesian y or a flat-Earth distance. The computational domain stays within a quarter turn of the launch radial to avoid angle wrapping.

The prescribed pitch θ is measured from **e**r toward **e**t. It holds its supplied initial value until `pitch_start_time`, varies linearly to its final value at `pitch_end_time`, then holds. During powered flight:

```
mdot = T / (Isp g0),  g0 = 9.80665 m/s²
m(t) = m0 − mdot t,   tb = (m0 − mdry) / mdot
rho = rho0 exp(−(r−R)/H)
Fdrag = −(rho Cd A / 2) |v| v
dr/dt = v
dv/dt = T/m (cos(theta) er + sin(theta) et) − mu/r³ r + Fdrag/m
```

At burnout, mass is exactly mdry; coast uses zero thrust and constant mass. A pitch value retained during coast records the supplied programme; with zero thrust it applies no thrust force and does not represent a computed vehicle attitude.

NASA describes point-mass translation as a simplifying rocket-motion model and distinguishes it from rotation and their coupling. The vector sum above specializes that model with zero lift and a prescribed thrust direction. [NASA basic rocket motion](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/basic-rocket-motion/).

NASA defines drag magnitude using density, speed squared, supplied coefficient and reference area. Here its direction is opposite velocity because the atmosphere is explicitly stationary. A constant coefficient is a supplied approximation; the cited equation does not validate that coefficient over changing flight regimes. [NASA drag equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/), [NASA rocket aerodynamics](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-aerodynamics/).

Constant mass flow follows NASA's specific-impulse relation. The zero-gravity, zero-drag, zero-pitch reduction is checked against the ideal rocket equation and its integrated displacement. [NASA specific impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/), [NASA ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/).

## Numerical contract

Classical RK4 uses distinct segments ending exactly at steering boundaries and burnout, then coast. Nonzero segments each use n, 2n and 4n steps on three aligned grids. Burnout has adjacent before/after samples with identical position, velocity and mass but different thrust. Algebraic mass is never advanced by an RK step.

Position-vector agreement uses displacement from launch as its relative scale, avoiding an Earth-radius-sized allowance. The inherited token `altitude_numerical_tolerance` supplies the absolute **position-vector** tolerance in metres for this adapter; `velocity_numerical_tolerance` supplies the vector-velocity tolerance. The catalog describes vector-state agreement; the reference input source explicitly records the inherited token’s meaning. Sampled metric allowances combine declared tolerances and observed grid differences. They are estimates, not rigorous error bounds. Numerical gaps and overlapping criteria remain unassessed.

Retained-artifact verification checks input/source identity, frame, force fields, mass, events, metrics and diagnostics without solving the differential equation again. It checks consistency, not authenticated truth or physical validity.

## Separate numerical implementation

`tests/test_guided_ascent_reference.py` writes its own five-state equations (x,y,vx,vy,m). It integrates mass as a state and constructs inertial thrust using atan2 plus pitch, without using the production force, schedule or segment helpers. Adaptive SciPy DOP853 uses rtol 2×10⁻¹² and atol 10⁻¹⁰, segmented at declared boundaries, with dense output compared at retained production times. [SciPy solve_ivp and DOP853 documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).

Four constructed cases include positive and negative turns, a late stronger turn and thin atmosphere. Acceptance is maximum vector-position difference below 0.0005 m, vector-velocity difference below 0.000003 m/s and mass difference below 0.00000001 kg. [Recorded results](GUIDED_ASCENT_REFERENCE_RESULTS.json) include the actual differences and reference-library version. This compares numerical implementations of the stated assumptions; it is not independent hardware, flight or human engineering validation.

Reproduce in a separate development environment with SciPy installed:

```console
python tools/guided_ascent_benchmarks.py --output docs/GUIDED_ASCENT_REFERENCE_RESULTS.json
python -m unittest discover -s tests -p test_guided_ascent_reference.py -v
```

The application still requires only the standard library. Without the optional development dependency, the SciPy unittest is explicitly skipped; it must not be reported as a passed reference check.

## Applicability limits

All engine, mass, atmosphere, coefficient, area and steering inputs are supplied and unverified. This model excludes rotation, wind, lift, 3D or six-degree-of-freedom motion, attitude, actuator authority, stability, closed-loop guidance/navigation, varying thrust/Isp, staging, reserves, aeroheating, reentry and landing. Computational bounds reject unsupported liftoff, surface crossing, unresolved schedules and trajectories outside the retained domain. Passing sampled criteria does not establish physical applicability, mission completeness or launch authorization.
