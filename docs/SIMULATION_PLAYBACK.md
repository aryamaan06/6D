# 6D — simulation and visual playback

October 17 integration update: explicit project orbital models now produce canonical trajectories and sampled/final-state requirement findings through the shared review engine. Project evidence playback is a read-only view of that exact saved artifact. The separate scenario contract below still describes Exploratory scenarios; it cannot change project requirements. See ORBITAL_WORKFLOW.md for model bindings, reuse and Assistant context.

Updated October 17, 2026, Asia/Calcutta. The first bounded 3D orbital implementation is connected to the existing project workspace. Broader space-system simulation remains part of the same product. The October 21 submission takes a verified snapshot; it does not redefine the startup scope.

## What works

Choose **Simulation** in the workspace toolbar. Configure an explicit orbital scenario, calculate locally, and save the returned trajectory. The viewer reads the saved states: it never asks a language model to invent motion.

- Three-component position and velocity propagated in a nonrotating body-centered inertial XYZ frame.
- A rotatable, zoomable orthographic 3D scene plus fixed XY, XZ and YZ projections. The same spatial scale is used on every axis.
- Play, pause, restart, playback-rate selection and a discrete-sample timeline. Exact SI position, velocity, radius, speed, energy and time are inspectable.
- Synchronized radius, speed, XYZ-position and specific-orbital-energy histories. Chart scales adjust to the data range; circular-orbit numerical variations can consequently appear magnified.
- Immutable saved runs attached to an exact project revision, with the complete scenario, project snapshot, source fingerprints, method, diagnostics and result samples.
- Compatible saved-run comparisons within the same project, including earlier revisions. Each comparison marker uses its own nearest saved sample, with its actual sample time shown. Outside the comparison run's duration, no comparison sample is displayed. Comparison aligns elapsed time from each supplied initial state, not a common calendar epoch.
- JSON export and reopening history without recalculation or inference. Changed solver sources mark previous receipts historical; they do not rewrite them.

The viewer uses a camera projection of computed XYZ states. Canvas rendering is a display choice; the underlying propagation is fully three-dimensional. Under a central force, any one supported orbit lies in its own orbital plane, which may be inclined to the reference axes.

## Model and applicable domain

The native solver applies Newtonian point-mass central gravity to an unforced elliptic trajectory. It integrates all coordinates using fixed-step, second-order velocity Verlet with internally nondimensionalized calculations. Each integration step is stored; there is no client-side integration, smoothing, fabricated intermediate sample or decimation. Lines connect recorded samples for presentation.

The strict `sixd.orbit-scenario.v1` input contains:

| Field | Meaning |
| --- | --- |
| `name`, `source` | Scenario name and explicit provenance/assumptions |
| `mu_m3_s2` | Central gravitational parameter, m³/s² |
| `exclusion_radius_m` | Spherical domain boundary, m |
| `position_m` | Initial [x, y, z], m |
| `velocity_m_s` | Initial [vx, vy, vz], m/s |
| `duration_s`, `steps` | Propagation duration and fixed integration count |
| `frame` | `body_centered_inertial_3d` |
| `schema` | `sixd.orbit-scenario.v1` |

Unknown fields, missing fields, nonfinite values, implicit units and unsupported frames are rejected. The numerical domain requires a bound orbit, eccentricity at most 0.9, analytic pericenter above 1.01 times the exclusion radius, and at most eight orbital periods. Work is limited to 16–4096 steps; the time step must resolve pericenter motion (`dt * pericenter_speed / pericenter_radius <= 0.02`). Supported scalar magnitude bounds and a minimum dimensionless time step also prevent ill-conditioned or unbounded runs. A trajectory reaching the exclusion radius fails without saving a completed receipt.

The reference scenario is constructed with Earth-like gravity and an inclined circular initial state. It has no measured vehicle, flight or CAD provenance. The shaded sphere depicts the supplied exclusion radius, not terrain, atmosphere or certified geometry. The point marker is deliberately enlarged for visibility.

## Relationship to project review

Orbital scenario inputs are **separate explicit data attached to a saved project revision**. They are not inferred from propulsion, beam, thermal or drag inputs. Changing a static project value does not automatically change the scenario or create a physical coupling. The complete project snapshot and its digest make that association inspectable.

Simulation does not currently create or alter canonical project requirement findings. A numerical diagnostic is not an engineering pass/fail verdict, and a recorded scenario is not an approved mission. General dynamic requirement mappings, physical coupling and model-dependent invalidation are further work. Draft project edits must be saved or discarded before running a scenario. Historical replay remains available with its saved revision stated.

Compatible overlays require the same project, scenario schema, gravity, frame, exclusion radius, method/force model, units and source fingerprints. Initial states, durations and step counts may differ; the comparison identifies changed fields and retains each run's samples. Different-duration extrema cover different time intervals. No orbital rendezvous, collision avoidance or uncertainty claim is inferred from an overlay.

## Evidence and numerical verification

Receipts preserve the solver source loaded at execution and the storage-contract source. Reads verify the unsigned receipt digest and exact project binding without invoking today's solver. Source changes block new execution until restart. A bounded single-run lock prevents parallel requests from creating an unbounded compute queue. All simulation execution is local and makes no model-provider request.

Independent mathematical tests cover an inclined circular reference, an eccentric orbit from Kepler's equation, arbitrary rotation, second-order refinement, reversibility and dimensional similarity. These are numerical checks for the stated model, not physical-test or flight validation. Energy and angular-momentum drift diagnostics alone do not bound trajectory phase or position error. Sampled extrema do not certify extrema between samples.

The model's state/units interpretation and circular/Kepler references are consistent with the primary [JPL NAIF two-body propagation documentation](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/prop2b_c.html), consulted October 17. 6D uses its own fixed-step numerical implementation; it does not call SPICE or claim SPICE equivalence, certification or endorsement. Recorded acceptance results belong in [SIMULATION_ACCEPTANCE.md](SIMULATION_ACCEPTANCE.md).

## Explicit remaining coverage

This increment does not calculate launch or landing, thrust or burns, changing mass, attitude/rotation, GNC, atmosphere/drag, aerodynamic heating, thermal transients, structural dynamics, oblateness, third-body gravity, relativity, physical contact, uncertainty or whole-vehicle reliability. External solver import, CAD geometry, simulated requirement findings and physical-test comparisons remain future integrations. These capabilities require their own applicable models and validation.

The full product goal remains evidence-linked behavior across supported space projects: useful motion and histories during design review, comparison with physical tests when available, and rechecking after changes. A visually convincing replay never substitutes for adequate engineering evidence.
