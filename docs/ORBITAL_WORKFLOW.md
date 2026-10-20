# Simulation in the engineering workflow

This increment connects the existing bounded three-dimensional orbital solver to the shared project, requirement, revision and evidence workflow. The numerical force model and integrator are unchanged. This is one supported domain in 6D; it does not establish whole-rocket or mission readiness.

## Connected journey

1. Open **Simulation → Project evidence → Open orbital review template**, or choose the orbital template from **Import project**. Review its details and create a project. The supplied inputs and limits are explicitly constructed examples.
2. Run the saved project's checks. The orbital adapter calculates one trajectory, stores its samples in the immutable review and derives the declared metrics from those same samples. The independent thermal model also runs.
3. Open **View trajectory** from a model, requirement or report. Playback and related findings refer to the exact saved review. Viewing, comparing and exporting do not execute the solver.
4. Choose **Review / edit inputs**, edit the draft in Table or Inspector, and preview its dependency impact. Save a new revision, then rerun affected checks. The preceding trajectory stays historical until evidence is explicitly calculated or reused for the new review.
5. Inspect current and historical criteria, actual sample histories, numerical limitations and source identities. Open a linked requirement or its Assistant from the trajectory. The Assistant can read that saved evidence and perform one reproducibility recheck; it cannot change the canonical verdict.

The **Exploratory scenarios** mode retains the earlier independent scenario workflow. Its freeform inputs are attached to a saved project revision but are not adopted as project model inputs or requirement evidence. A decorative animation or standalone exploratory run cannot make a requirement pass.

## Explicit orbital model contract

The `orbital_trajectory` adapter uses the existing `sixd.project.v1` schema. Each input is a numeric scalar record containing value, exact unit and source. All model parameters are required, with no inferred values or unit conversion:

| Parameter | Unit |
| --- | --- |
| `mu_m3_s2` | `m^3/s^2` |
| `exclusion_radius_m` | `m` |
| `position_x`, `position_y`, `position_z` | `m` |
| `velocity_x`, `velocity_y`, `velocity_z` | `m/s` |
| `duration_s` | `s` |
| `steps` | `1` (integer-valued) |

The frame is explicitly fixed to nonrotating, body-centered inertial Cartesian coordinates; elapsed time starts at the supplied state. This contract supplies no ephemeris date, axis orientation relative to another frame, terrain or body shape. The bounded kernel's ellipticity, clearance, duration and time-resolution restrictions still apply; see [SIMULATION_PLAYBACK.md](SIMULATION_PLAYBACK.md).

Five metrics can be mapped to project requirements: `min_radius_m`, `max_radius_m`, `max_speed_m_s`, `final_radius_m` and `final_speed_m_s`. Extrema cover the stored integration samples over the declared duration. Final metrics use the last sample. Neither establishes an unsampled continuous-time bound. Numerical conservation diagnostics remain diagnostics and cannot be mapped as supported engineering metrics through this adapter.

Requirement comparison uses the same explicit operator and same-unit limit rules as other maintained models. A calculated limit violation is `not_met`. Invalid solver inputs, unsupported metrics or unit mismatches are `not_assessed`. A supported `met` result is limited to its stated numerical model, grid and window. No uncertainty or numerical-error allowance is inferred.

## Revisions and provenance

- Changing a bound state, gravitational parameter, duration, step count or its source invalidates that model's prior applicability. Rerun calculates a new trajectory.
- Changing only a requirement limit reuses the unchanged trajectory and compares it against the new limit. The new review records the original execution run and revision.
- Changing an unrelated thermal input does not infer a physical coupling. Only the explicitly dependent thermal model reruns.
- Old reviews and standalone receipts remain immutable. Source changes can make them historical but cannot rewrite their samples or old findings. Historical three-source reviews remain readable alongside newer reviews that also fingerprint the orbital adapter and solver.
- Project playback IDs identify derived views of canonical saved runs. Their digest is a consistency check on that view; the canonical run digest, review digest and original model execution identity remain visible. No second simulation is created for playback.
- Comparison requires compatible physics, units, frame and method. Different windows and grids keep their own sample times. Imported arbitrary calculation results are not accepted as evidence.

## Assistant and scope

The Assistant's existing provider and spending configuration are preserved. Orbital tool responses send an explicitly labelled summary with the saved scenario, method, diagnostics, artifact digest and at most five actual witness samples. Full samples remain in the canonical review and local investigation receipt. Reproducibility compares the complete results before reducing context for the model; summaries do not replace that comparison.

Guidance asks for source/frame checks, time-step refinement and independent reference evidence, and identifies excluded effects. No paid provider call is necessary to create, calculate, revise, replay, compare or export the engineering evidence. Offline Assistant tests establish orchestration and evidence handling, not new live model quality.

This remains unforced two-body point-mass translation. Thrust, launch/landing, GNC, atmospheric effects, perturbations, heat transfer, structural response, uncertainty and physical-test validation are not inferred from the orbital trajectory. An independent thermal calculation in the reference project is deliberately not a coupled orbital thermal simulation.
