# Numerical accuracy

Delivered October 23, 2026, local build `a6215d46280d`.

New orbital calculations use classical fourth-order Runge–Kutta (RK4), with up
to 16,384 integration steps. Saved Velocity Verlet calculations keep their
original method, samples, findings and second-order assessment policy.

## Try the connected workflow

1. Open http://127.0.0.1:8768/ and refresh; confirm the build above in the footer.
2. Choose **Simulation → Project evidence**. If the project has no orbital
   model, choose **Open orbital review template**, review the constructed inputs
   and explicitly create the project.
3. Click **Run affected checks**, then **View saved trajectory**. Inspect the
   numerical-accuracy panel, linked findings, playback and charts.
4. Expand **Numerical diagnostics, sources & coverage** for the recorded method,
   order and step size. The full report and exported JSON retain the same evidence.
5. Use **Review / edit inputs** or the shared Table/Inspector to change inputs.
   The orbital model definition editor holds position/velocity accuracy criteria
   and their rationale. Save a revision and explicitly rerun affected checks.

No AI key is needed. Exploratory scenarios remain separate from project findings;
they do not acquire a numerical pass merely because their animation looks smooth.
Existing results can be marked historical after this source update. Opening the
application does not recalculate them.

## What changed

- Orbital adapter version 3 records RK4 solver version 2, order 4. The legacy
  adapter/version and solver pairings remain accepted for retained evidence.
- Three retained grids compare signed position and velocity at aligned times.
  RK4 checks observed order against 3.7–4.5 and the supplied difference tolerances.
  Legacy Velocity Verlet evidence keeps its original second-order policy.
- Missing criteria, unavailable coarse grids, inconclusive order and excessive
  differences leave numerical accuracy unresolved. These gaps continue through
  requirements, scalar links, playback and reports.
- Fractional powered-flight cutoff times now use identical explicit segment
  endpoints. This removes a one-floating-point-step timing inconsistency at
  burnout. Powered-flight adapter/solver version 2 retains compatibility with
  version 1 artifacts. Source identity is captured when its implementation loads.
- The orbital final timestamp is explicitly pinned to the declared duration,
  including non-power-of-two step counts. Larger saved trajectories reopen from
  retained evidence without invoking the current integrator.

## Limits

The physics remains bounded, unforced, elliptic point-mass two-body translation.
Existing eccentricity, duration, clearance and pericenter-resolution checks
remain. Increasing the step ceiling does not guarantee every eight-period or
high-eccentricity input will be accepted by all three grids. Scenario-study total
work limits also remain in force.

RK4 is not symplectic: improved measured finite-duration error does not establish
indefinite energy conservation. Three-grid agreement is empirical evidence, not
a rigorous bound on true error; near roundoff its order can be inconclusive.
Requirement extrema remain sampled, not continuous-time guarantees. This adds no
perturbations, staging, steering, landing or flight certification.

See [measured results](NUMERICAL_ACCURACY_RESULTS.md) and the
[acceptance criteria](NUMERICAL_ACCURACY_ACCEPTANCE.md).
