# Independent orbital reference benchmarks

The initial comparisons found maximum state-position errors of **14.56 km over
7.5 circular periods**, **8.38 km over four moderately eccentric periods**, and
**6.43 km over one e = 0.6 period** at the 4,096-step ceiling. These are useful
error characterizations, **not mission-grade accuracy or certified error
bounds**. Broad regression levels passed; that does not make these errors
acceptable for an actual mission requirement.

This is development verification of `orbital_trajectory` and its delegated
velocity-Verlet simulation kernel against an independently implemented tool.
It is not physical-test, flight or mission validation. All orbital elements
and the Earth-like gravitational parameter are constructed inputs.

## Sources actually inspected

- [NASA/JPL NAIF `prop2b_c`](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/prop2b_c.html):
  propagates a two-body initial state through a universal-variable formulation;
  its input state, gravitational parameter and elapsed time must use coherent
  units. Its circular example gives `speed = sqrt(mu/r)` and a half-period
  sign reversal. The document identifies Danby, *Fundamentals of Celestial
  Mechanics*, second edition, pp. 168–180, as its derivation reference.
- [NASA/JPL NAIF `conics_c`](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/conics_c.html):
  defines the eight supplied elements and their units. This routine constructs
  initial states from declared pericenter, eccentricity, inclination, node,
  periapse argument, anomaly, epoch and gravitational parameter.
- [SpiceyPy documentation](https://spiceypy.readthedocs.io/en/v8.3.0/):
  the separately maintained Python wrapper of the NAIF SPICE toolkit. The
  external reference used here is the bundled CSPICE library, not a rewritten
  Python orbital integrator.

The sources were opened on October 19, 2026. Their reference scope is ideal
two-body dynamics; this benchmark does not imply NASA endorsement of 6D.

## Reference separation and reproducibility

`tools/published_orbit_benchmarks.py` exports `run_checks()`. It calls the
production project adapter only to obtain **actual** results. Reference states
come from external CSPICE `prop2b` at every actual sample time. The reference
does not call production acceleration, propagation, orbital-element extraction,
conservation diagnostics or receipt-validation functions.

Initial eccentric/inclined states come from CSPICE `conics` in km and km/s and
are explicitly multiplied by 1,000. Propagation uses `prop2b` in coherent SI,
so its state output already has metres and metres per second. No ephemeris
kernels or network calls are required while running checks.

The analytic circular reference independently computes all six state
components using sine/cosine with supplied radius, speed and inclination. Its
orbital period comes from the published circular-speed relation. The eccentric
refinement reference uses CSPICE, not an in-project Kepler solver.

The reference dependency is isolated from the application in
`.local/benchmark-deps`. No production dependency or solver was changed by the
benchmark. The inspected local versions were **SpiceyPy 8.3.0**, **CSPICE_N0067**
and **NumPy 2.3.5**. Missing or mismatched SpiceyPy raises a controlled error;
there is no silent analytic replacement for the external comparison.

From the repository root, using a Python interpreter with NumPy installed:

```powershell
python -m pip install --target .local/benchmark-deps --no-deps --only-binary=:all: spiceypy==8.3.0
python tools/published_orbit_benchmarks.py > work/published-orbit-results.json
```

The runner prints JSON rows and exits nonzero if any row fails. The parent
benchmark suite also imports these rows. Installation is a development action;
running 6D does not require SpiceyPy.

## Acceptance levels declared before execution

- Each completed SPICE comparison: maximum vector position error / supplied
  semimajor axis ≤ **0.02**; maximum vector velocity error / `sqrt(mu/a)` ≤
  **0.02**. This uses vector errors and catches phase/direction errors that
  scalar radius/speed checks can miss.
- Each of the five project metrics compared on the identical discrete grid:
  relative error ≤ **0.01**.
- Circular and eccentric refinements at 1,024, 2,048 and 4,096 steps: both
  measured position-error orders must lie within **[1.8, 2.2]**.
- Finest circular grid: maximum relative position and velocity errors ≤
  **0.00001**.

These are declared numerical benchmark levels, **not mission tolerances** or
universal error bounds. In particular, a 2% threshold is too loose for many
real orbit-design tasks. Passing does not establish suitability for them.
Conservation diagnostics are not used as a substitute for state error.

## Observed initial results

All four completed external trajectories compare **4,097 states** and all five
adapter metrics. The table preserves absolute errors so that broad relative
thresholds do not obscure practical numerical limitations.

| Constructed case | Window | Maximum position error | Maximum velocity error | Result |
| --- | ---: | ---: | ---: | --- |
| Circular, inclination 55°, a = 7,000 km | 7.5 periods | 14,560.564 m | 15.695490 m/s | Within declared benchmark levels |
| e = 0.25, inclination 63°, a = 12,000 km | 4 periods | 8,382.917 m | 5.889521 m/s | Within declared benchmark levels |
| e = 0.6, inclination 32°, a = 20,000 km | 1 period | 6,428.775 m | 4.535210 m/s | Within declared benchmark levels |
| e = 0.7, retrograde inclination 137°, a = 30,000 km | 0.75 period | 45.097 m | 0.008581 m/s | Within declared benchmark levels |

Circular observed orders were **1.9999850** and **1.9999963**. Eccentric observed
orders were **2.0000241** and **2.0000056**. This supports expected second-order
convergence on these cases. It does not prove global accuracy across the
permitted parameter space.

A separate exact-eight-period circular boundary case was initially rejected
before propagation: the period recovered from the floating-point initial
state was slightly shorter than the period calculated from the supplied
elements. The requested duration exceeded the recovered eight-period bound
by **3.638 × 10⁻¹¹ s**, or five ULPs at that duration. The suite preserves this
case and reports its actual outcome; it does not shorten the window to turn a
failure into a pass. The original row is retained in
`artifacts/published-benchmarks/pre-fix-orbit-boundary.json`. See the generated
parent results for the outcome against the final delivered production source.

## Remaining limitations

The long-window errors above show why energy/angular-momentum conservation and
small radius errors do not imply small position/phase errors. No result here
establishes a numerical-error allowance for user requirement verdicts. Users
must choose justified resolution/error margins for their own intended tasks.

No thrust, drag, nonspherical gravity, third bodies, changing mass, uncertainty,
hardware, launch/entry/landing or spacecraft navigation has been validated.
Discrete-grid extrema are compared; continuous-time extrema are not certified.
The external implementation strengthens algorithmic independence, while all
case selection and benchmark wiring still received AI assistance and remain
open to human review.
