# Explicit scalar calculation chains

6D can bind a supported calculation's scalar result to another supported calculation's parameter. Each connection selects a source model, source metric, exact unit and written physical rationale. Calculations run in dependency order; the resulting review retains both the connection and its upstream evidence.

This adds directed, one-way calculation chains. It does not introduce a simultaneous coupled solver, infer physical connections, or establish that two physically different quantities are interchangeable because they share a unit. Existing subsystem interface contracts remain separate comparisons against declared criteria.

## Workspace workflow

1. Open http://127.0.0.1:8768/ and choose **Calculation chains**. **Open constructed reference** opens the drag-to-beam example for explicit creation as a separate project.
2. Choose **Run saved checks**. The dependency graph identifies execution stages. Inspect a receiving model to see its selected source metric, resolved value, rationale and retained source identity.
3. For your own saved project, choose **Edit in shared draft**, then **Add calculation link**. Select the receiving model and parameter, source model and compatible metric. Supply the physical mapping and load-case rationale, then **Apply link to shared draft**.
4. Review the draft and **Save revision**. Run saved checks to calculate that revision. Draft graphs show proposed dependencies and have no new calculated values.
5. Edit a supplied upstream condition through the shared project editor. Preview the affected models and requirements before saving. After running, inspect which calculations executed and which independent results were reused.
6. **Open full report** includes connection evidence alongside the canonical findings. Exported receipts retain the full ancestor records. Scenarios use their own hypothetical cases and leave the saved project baseline intact.

A link replaces the receiving parameter's direct binding; the original supplied input record remains available. Removing a link can leave that parameter unbound until it is connected again or assigned a direct input through project authoring. The shared setup checks explain missing bindings.

## Connection contract

A model may include an optional `links` object. The keys are parameter roles for that receiving model. Each role must be supplied exactly once, either by a direct project input in `inputs` or by a metric connection in `links`.

```json
{
  "id": "beam",
  "type": "static_cantilever",
  "inputs": {
    "length": "beam_length",
    "young_modulus": "beam_modulus",
    "second_moment": "beam_second_moment",
    "outer_fiber": "beam_outer_fiber"
  },
  "links": {
    "tip_force": {
      "model_id": "aerodynamic_load",
      "metric": "drag_force",
      "unit": "N",
      "rationale": "For this constructed case, apply the entire drag-force magnitude as a transverse point load at the beam free end. Load direction, location and boundary conditions are declared assumptions."
    }
  }
}
```

The source model and metric must exist in the supported model catalogue. The declared link unit must equal both the source metric unit and receiving parameter unit literally. There is no implicit conversion, numerical scaling, sign change, rotation, summation or executable expression. The user supplies a nonempty rationale and remains responsible for its physical applicability.

Power-budget mode and load roles use the same explicit connection mechanism as their existing direct bindings. Domain restrictions still apply: for example, a linked step count or equipment count must satisfy that calculator's integer and range rules.

Projects with links are bounded to 128 models, 1,024 links and a dependency depth of 64. Self-dependencies and longer cycles are rejected. Malformed links, missing model/metric references, unsupported receiving roles and unit mismatches are rejected during setup validation. No partial numerical verdict is created for an invalid project definition.

## Execution and results

Sources execute before their dependants, regardless of the order of the models in the imported JSON. Independent branches can retain reusable results. A completed source calculation may feed downstream calculations even when one of its own requirements is not met: an unmet criterion is a calculated finding, not missing numerical evidence.

If a validly connected source cannot produce a result, its dependant stays **not assessed**, with empty numerical metrics and an explicit upstream reason. A downstream calculation whose resolved values violate its own model's domain rules remains **invalid inputs**. The application does not substitute a previous result, a direct-input fallback, zero or an AI prediction.

Requirement limits remain explicit project inputs. Connections do not change limits or convert a requirement's pass/fail state into a numerical parameter. Results continue to mean only what the selected models, conditions and supplied criteria support.

## Revisions, reuse and provenance

The configuration of a linked model includes its own model definition, all ancestor model definitions and the exact direct-input records consumed by that entire chain. Input value, unit and source labels all matter. A change to an upstream input, binding, metric selection or rationale therefore affects downstream evidence even when the resulting number happens to stay the same.

Changes to unrelated branches can reuse their existing calculations. Requirement-only changes can reuse unchanged calculation results while comparing them against the new criterion. Dependency previews identify the affected chain before execution; they do not predict whether the new design passes.

Linked calculation results retain a `calculation_inputs` object with schema `sixd.calculation-inputs.v1`:

- `dependency_fingerprint`: digest of the target and ancestor configuration.
- `values`: the resolved parameter values and units available to the receiving calculation.
- `links`: each selected source, metric, unit, rationale, source-result digest, source-configuration digest and source status.
- `ancestors`: each upstream model's definition, direct-input records, original result digest and configuration digest.

A source-result digest covers the original same-review result, including its own upstream connection evidence when present. Reading a saved review checks these relationships against the retained snapshots without integrating a trajectory or rerunning the calculation chain. Historical source data remain historical; unsigned digests detect inconsistent records and do not authenticate external data or establish physical truth.

Legacy projects without links retain their previous record shapes and remain readable. No connection is injected into old projects, direct inputs or saved reviews. The verifier includes the maintained `chains.py` source while accepting complete historical source sets.

## Independent constructed example

Consider one supplied atmospheric condition with density `0.4 kg/m^3`, relative speed `10 m/s`, drag coefficient `0.5` and reference area `2 m^2`. These are synthetic demonstration values, not a real vehicle specification.

The analytical dynamic pressure is `q = rho*v^2/2 = 20 Pa`, and drag magnitude is `F = q*Cd*A = 20 N`. Explicitly declare that this force is the entire transverse tip load on a uniform cantilever with length `2 m`, Young's modulus `2e11 Pa`, second moment `1e-6 m^4` and outer-fibre distance `0.01 m`.

Under the stated linear beam assumptions:

- Maximum bending stress is `F*L*c/I = 400000 Pa`.
- Tip deflection is `F*L^3/(3*E*I) = 1/3750 m`.

The constructed template declares a `10 N` drag limit, `1000000 Pa` bending-stress limit and `0.001 m` deflection limit. Its drag criterion is deliberately not met while both structural criteria are met, demonstrating that valid numerical evidence remains usable after a failed criterion. A separate steady thermal calculation demonstrates an independent branch.

Changing speed to `20 m/s` multiplies force, stress and deflection by four. Changing density to `0.1 kg/m^3` at the same time returns the force to `20 N`; the downstream calculation still needs fresh evidence because the upstream condition changed. Negative density makes the source calculation invalid, so its connected beam result is unassessed. None of these examples independently validates the drag coefficient, structural load distribution or beam assumptions.

## Scope of evidence

The feature transfers explicitly selected scalar results among already supported adapters. It adds no CFD, distributed-load reconstruction, vector/frame conversion, time-series coupling, feedback iteration, multi-physics convergence proof or whole-mission readiness assessment. Physical source applicability and the rationale for each connection require engineering review. Local calculations and review reads require no paid model call.
