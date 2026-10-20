# External references for four static engineering adapters

Sources read October 19, 2026. This document accompanies
`tools/published_static_benchmarks.py`. The ten checks consist of two coarse
published worked examples, five constructed cases evaluated from published
equations, and three domain-guard checks. A passing result means agreement with
the named mathematical reference within the recorded tolerance. It does not
establish hardware validity, a complete engineering discipline, or independent
human review.

The reference functions use 60-digit `Decimal` arithmetic. They do not import
production constants, parameter registries, solver functions, or reference
fixtures. Production `engineering.evaluate_models` is called only to obtain
actual results. The executable suite is offline; source URLs and retrieval date
are recorded here rather than silently fetching potentially changed pages.

## Propulsion

[NASA Glenn: Ideal Rocket Equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/)
states the ideal mass-ratio relation and gives a rounded worked illustration:
specific impulse about 350 s, delta-v about 25,000 ft/s, mass ratio about 10 and
propellant fraction about 90%. The benchmark converts 25,000 ft/s to 7,620 m/s
and projects calculated consumed mass back to fraction and mass ratio. Input
mass and thrust are arbitrary normalization choices, not NASA vehicle data.
Tolerances are deliberately coarse: 0.02 absolute fraction and 10% mass ratio.
These are rounding sanity checks, not a precise orbit-insertion benchmark.

[NASA Glenn: Specific Impulse](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/)
supports the constant effective exhaust speed and thrust/flow relation.
[NIST's current CODATA table](https://physics.nist.gov/cuu/Constants/Table/allascii.txt)
supplies conventional standard gravity 9.80665 m/s². A separate constructed
case uses mass 1,200 kg, dry mass 400 kg, delta-v 3,000 m/s, specific impulse
310 s and thrust 2,300 N. Independent exponential/impulse arithmetic checks all
five outputs. Zero delta-v and rejected negative delta-v are additional checks.
No drag/gravity/steering losses, staging, reserves, engine qualification or
trajectory are validated.

## Cantilever

[MIT Roylance: Stresses in Beams](https://web.mit.edu/course/3/3.11/www/modules/bstress.pdf),
printed page 4, Eq. 7, supplies bending stress from moment and outer-fiber
distance. [MIT 3.052 lecture appendix](https://ocw.mit.edu/courses/3-052-nanomechanics-of-materials-and-biomaterials-spring-2007/d8d2ffa0503ad0adf0edb741ddb4e4c8_lec2_appendix.pdf),
printed pages 2–5, derives the fixed-free beam with transverse tip force and its
tip displacement (Eq. 11). The constructed case uses F=4 N, L=0.8 m,
E=70 GPa, I=3.2×10⁻⁸ m⁴ and outer distance=0.004 m. Expected stress is
400,000 Pa and expected deflection is approximately 0.000304761904762 m.
These numerical inputs/outputs are not a published worked example.

The model assumes a uniform slender beam, rigid clamp, small deflection and
linear elasticity. This benchmark does not validate shear deformation,
buckling, vibration, fatigue, material allowables, real constraints or joints.

## Radiation

[NASA CR-1852: Portable Thermal Control Systems](https://ntrs.nasa.gov/api/citations/19720002481/downloads/19720002481.pdf),
printed page 35 (PDF page 44), Eq. 3-2, gives radiator exchange with an explicit
view factor and a difference of fourth powers. The benchmark specializes the
view factor to one and uses an isothermal grey surface viewing a black
isothermal background. It uses modern SI constants, not the report's rounded
1971 imperial Stefan–Boltzmann coefficient.

The [NIST table](https://physics.nist.gov/cuu/Constants/Table/allascii.txt) lists
the exact-SI defining values for h, k and c and the resulting Stefan–Boltzmann
constant. The reference computes sigma from these constants at 60 digits,
then takes two square roots. Production stores sigma rounded to ten digits;
relative temperature tolerance 2×10⁻¹⁰ includes this difference.

Constructed inputs are 321 W, 1.7 m², emissivity 0.84 and background 210 K.
This is an equation-based check, not a reproduction of the report's radiator
hardware or approximate sizing illustration. Emissivity above one must be
rejected. Thermal transients, gradients, conduction, convection, view-factor
geometry and actual environmental heating remain outside the calculation.

## Drag

[NASA Glenn: Drag Equation](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/)
provides the supplied-condition magnitude equation and dynamic pressure, and
requires compatible coefficient/area conventions. A strict constructed case
uses density 1.17 kg/m³, speed 17 m/s, coefficient 0.83 and area 0.42 m²;
expected pressure is 169.065 Pa and force is 58.936059 N.

[NASA Glenn: Smeaton Coefficient](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/smeaton-coefficient/)
also publishes a numerical low-speed flat-plate illustration. Its inputs are
converted to SI before adapter execution, then force is converted back to its
coefficient convention. The printed inputs give 0.003262805333 while NASA
prints 0.00327. Output-only rounding is insufficient: a density half-last-digit
interval contributes about 6.88×10⁻⁶, and output rounding contributes 5×10⁻⁶.
The adopted absolute interval is 1.2×10⁻⁵. This coarse check is not evidence of
a production bug; the strict Decimal case is separate. Negative speed magnitude
must be rejected. Coefficient applicability, Mach/Reynolds regime, lift,
moments, heating and trajectory are not established.

## Reproduction and interpretation

Run with the project's Python environment:

```text
python tools/published_static_benchmarks.py
```

The JSON includes exact case identities, units, source URLs, expected/actual
values, per-metric errors, tolerances and limitations. A nonzero exit status
means at least one comparison failed. The suite does not access saved projects,
spending ledgers, credentials or inference services.

The references provide external mathematical authority. The benchmark code is
still authored within this project, so common conceptual mistakes remain
possible. External specialist review and real experimental validation are
separate outstanding evidence.
