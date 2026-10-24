# Staged ascent: equations and reference checks

Checked October 24, 2026. This extends the declared planar point-mass force model documented in [GUIDED_ASCENT_REFERENCES.md](GUIDED_ASCENT_REFERENCES.md). The new adapter keeps constant per-stage specific impulse, supplied piecewise-linear thrust, prescribed steering and ideal serial separation. Real engine, guidance and separation feasibility are unassessed.

## Stage and fuel accounting

Initial attached mass equals payload plus every stage's dry and propellant masses. Only the active stage expends propellant. During a linear thrust segment, with stage-local segment time τ:

```
T(τ) = T0 + (T1−T0) τ / Δt
J(τ) = T0 τ + (T1−T0) τ² / (2 Δt)
consumed propellant = accumulated J / (Isp g0)
g0 = 9.80665 m/s²
```

Fuel exhaustion is the earliest resolved time when accumulated impulse reaches the declared stage propellant times Isp g0. The supplied profile can extend beyond that time; unused duration is reported instead of continuing to burn nonexistent fuel. Insufficient total impulse is rejected. Inputs within the stated floating-point endpoint tolerance are pinned to an exact declared thrust knot rather than generating an almost-coincident event.

NASA relates thrust, mass flow and specific impulse and defines impulse as integrated thrust. The constant-Isp conversion above specializes those relations to supplied thrust segments. [NASA specific impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/), [NASA rocket thrust equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-thrust-equation/).

At a nonfinal stage's burnout, the engine first cuts off, then the empty stage's declared dry mass is discarded. Position and velocity remain continuous under the explicit zero-separation-impulse assumption. The discarded material is assumed to depart with the instantaneous vehicle velocity. A supplied interstage coast follows before upper ignition. Final-stage dry mass remains attached. This accounts for mass; it does not solve separation mechanics or the discarded stage's subsequent trajectory. NASA describes staging as discarding vehicle mass, commonly followed by upper-stage ignition. [NASA flight to orbit](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/flight-to-orbit/), [NASA rocket weight](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-weight/).

`burn_duration` is the sum of stage operating intervals through exhaustion, including any zero-thrust portions within a supplied profile. `total_duration` also includes interstage delays and final coast. Burned propellant and jettisoned dry mass are separate quantities. The mass identity is:

```
initial mass − consumed propellant − discarded dry mass = final retained mass
```

For zero gravity, zero drag and vertical steering, velocity increments reduce to the sum of each stage's ideal rocket-equation increment. Dry separation itself supplies no velocity increment. [NASA ideal rocket equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/).

## Integration and retained evidence

Classical RK4 stops at every relevant thrust/pitch boundary, exact exhaustion, separation and ignition. Coincident events retain their ordered sides at the same timestamp. Mass and engine force can change; position and velocity cannot jump under this model. Three grids compare aligned vector states and sampled metrics. Position tolerances use displacement from launch, not central-body radius, as the relative scale.

The artifact retains parameters, supplied/used stage profiles, stage timeline, fine/intermediate samples, event indices, numerical diagnostics and source identity. Its verifier checks internal consistency without rerunning the differential equation. Digests and consistency do not establish authenticated or physical truth. Numerical allowances and sampled maxima are not rigorous continuous-time bounds.

## Separate adaptive reference

`tests/test_staged_ascent_reference.py` writes a different six-state ODE for x, y, vx, vy, total mass and active-stage propellant. SciPy DOP853 integrates both mass and fuel and locates exhaustion using a terminal zero-fuel event. It does not call the production force, analytic impulse root, mass, stage-plan or event-layout helpers. Before/after dry-mass snapshots are applied explicitly at independently located reference burnouts. See [SciPy solve_ivp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).

Four constructed cases cover the interactive two-stage reference, zero separation/ignition delay, reduced upper-stage Isp and a negative turn with a longer delay. Declared limits are 0.02 m maximum sampled vector-position difference, 0.001 m/s vector-velocity difference, 10⁻⁷ kg mass difference and 10⁻⁸ s event-time difference. [Recorded parameters, differences, dependency version and source hashes](STAGED_ASCENT_REFERENCE_RESULTS.json).

Reproduce in a separate development environment with SciPy installed:

```console
python tools/staged_ascent_benchmarks.py --output docs/STAGED_ASCENT_REFERENCE_RESULTS.json
python -m unittest discover -s tests -p test_staged_ascent_reference.py -v
```

Without that optional dependency the SciPy unittest is explicitly skipped. The application remains standard-library-only. These are different numerical implementations of the same supplied assumptions, not independent hardware or flight validation.

## Bounds

One to four serial stages; one to six linear thrust segments per stage; positive masses/Isp; nonnegative thrust; a resolved immediate liftoff; bounded total time, grid work, altitude, speed and angular travel. Negative, incomplete, insufficient or unresolvable inputs are model/input gaps. The final separation delay must be zero because final dry mass is retained.

No parallel boosters, crossfeed, variable Isp, impulse from separation, falling-stage propagation, changing aerodynamic geometry, lift, wind, rotation, 3D attitude, slosh, flexible structures, actuator or closed-loop guidance response, aeroheating, entry, recovery or landing. The supplied global drag coefficient and area remain constant across stage changes; users must supply an appropriate model/evidence before relying on that approximation.
