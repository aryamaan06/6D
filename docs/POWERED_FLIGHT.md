# Powered vertical flight

Delivered October 23, 2026, build `cedf1afe772d`. Open
[6D](http://127.0.0.1:8768/) and refresh. This calculation needs no AI key.

## Try the working example

1. Choose **Powered flight** in the left sidebar.
2. Choose **Use constructed flight reference**, inspect the preview, then
   **Create project**. This creates a separate example project.
3. Choose **Powered flight** again, then **Run checks**.
4. Use **Play**, the sample slider, and the before/after cutoff buttons. Inspect
   the six charts for altitude, velocity, mass, dynamic pressure, acceleration,
   and thrust/drag. The vertical marker depicts recorded altitude, not vehicle
   geometry or a three-dimensional trajectory.
5. Open a requirement's evidence or the full report. The combined review JSON
   includes the retained trajectory, refinement grids, inputs and diagnostics.

The constructed reference consumes 300 kg of propellant during a constant-thrust
burn and then coasts for 20 seconds. All values are illustrative inputs, not a
vehicle design recommendation or flight measurements.

## Change a design and review its consequences

Choose **Edit flight inputs**, enter the shared draft, change a sourced input, preview the
affected checks, save the revision, and run checks again. Playback is suppressed
while a draft is active. Old runs remain available under their original revisions.
In the constructed example, changing thrust from 20000 N to 11000 N causes the
declared 5000 m burnout-altitude criterion to be unmet. This is an example of a
calculated finding under the stated model assumptions.

For your own supported case, use **Author project** to bind explicit SI inputs
and requirements to **Powered vertical flight**. Existing models can use its
approved scalar metrics through explicit calculation chains. These links do not
create simultaneous multidisciplinary physics.

## What the calculation covers

The model starts at rest at a supplied reference radius. It combines constant
upward thrust and specific impulse, decreasing mass, inverse-square gravity,
and signed drag in a stationary exponential atmosphere. It stops the burn at
the supplied dry mass and can continue through above-surface coast, including
descent before surface crossing. It retains both sides of instantaneous cutoff.

Three RK4 grids support an empirical numerical-agreement check. Failed agreement
leaves diagnostic plots visible but blocks assessed requirements and downstream
scalar use. A threshold overlapping a numerical allowance remains **Not assessed**.
Sampled maxima are not guaranteed continuous maxima, and grid agreement is not
a rigorous error bound or physical validation.

This model does not cover steering, staging, horizontal flight, winds, variable
engine performance, aeroheating, reentry, landing, or a complete launch-to-orbit
mission. Surface crossing and insufficient initial thrust are rejected. Existing
orbital playback remains a separate supported calculation.

See [verification results](POWERED_FLIGHT_RESULTS.md) and
[equations, references and numerical limits](POWERED_FLIGHT_REFERENCES.md).
