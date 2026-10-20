# Project creation and engineering authoring

This increment lets users build a project directly in the local workspace. It uses the same project records, calculation adapters, revisions and evidence as JSON imports and reference templates.

## Working sequence

1. Choose **New project**. Supply a project ID, name, purpose and assumptions, and lifecycle stage. Creation saves an empty revision R1 and runs no calculations.
2. Open **Author project → Edit draft**. Add numerical input records, including each value, exact unit and source. Requirement limits are input records too.
3. Add a supported model. Bind its named parameters to supplied input records. Inspect the adapter's assumptions and exclusions. The form does not invent numerical input values.
4. Add requirements. Each needs a title, model, produced metric, explicit comparison operator, supplied limit input and criticality.
5. Use **Validate setup** to inspect missing bindings, incompatible units and unsupported metric mappings. This is read-only configuration guidance, not a numerical result or engineering pass.
6. Preview the dependency impact and save a new revision. Run checks for the saved configuration, then inspect its findings and report. Orbital models also expose their exact saved trajectory in Simulation.
7. Edit an input, binding, requirement or project description in a new draft. Preview changes, save, rerun affected models, compare the evidence and retain the original revision.

The shared draft also appears in Canvas, Table and Inspector. Existing draft discard and unsaved-change navigation protection apply. IDs remain fixed after adding records; replacing an adapter requires an explicit new model and requirement remapping. Model and input removal is blocked while another record references it. Remove or remap dependents first. No dependent records are silently deleted.

## Data and assessment boundaries

Empty project skeletons can be saved and reopened. They have no current review, verdict, execution receipt or evidence report. The workspace rejects calculation while models or requirements are absent. Saving an empty later revision does not delete earlier reviews.

The strict `sixd.project.v1` record fields remain unchanged. Purpose and author-supplied assumptions are recorded in project description and optional model description; they do not override the maintained adapter's numerical assumptions. Each input still requires a finite numeric value, explicit unit and nonempty source. No implicit conversion occurs, and an empty value is not zero. A supplied source label is not independent validation of that source.

Supported authoring choices use the five maintained adapters: ideal propulsion, static cantilever, steady radiative equilibrium, single-condition drag and bounded sampled two-body orbital trajectory. Model-type groups in the canvas follow explicit bindings. General arbitrary hierarchy editing and inferred physical coupling remain future work.

The setup preflight checks structural record validity, binding completeness, exact units and known output metrics. It does not run physics, enforce every adapter-specific numerical domain, predict outcomes or establish applicability. Those checks remain with the existing adapters. Imported unsupported models remain representable with explicit evidence gaps; a model catalog cannot manufacture their solver or metric evidence.

Record creation and setup validation do not invoke AI. Existing requirement-scoped investigations still require a fresh saved review and an explicit live start. Model selection, private key handling and cumulative spending accounting are unchanged.

## Read-only interfaces

- `GET /api/model-catalog` returns maintained model types, exact parameter and output units, versions, assumptions, exclusions, supported operators and lifecycle-stage labels. It contains no numerical defaults.
- `POST /api/authoring/preflight` accepts exactly `{project}` and returns `sixd.authoring-preflight.v1`: `can_run`, error/warning issues with record paths, and record counts. It never executes a model or saves a project.
- Existing `/api/projects`, `/api/impact`, `/api/revisions` and `/api/run` continue to own persisted creation, preview, immutable revision save and calculation.

Workspace snapshot validation explicitly permits empty model/requirement collections. Strict lifecycle review validation retains its existing nonempty contract, preventing empty configuration from becoming a successful review. Stored historical schemas and receipts are preserved; changed verification sources make older evidence historical until a deliberate rerun.

This milestone adds authoring, not new engineering physics, customer validation, hardware qualification, team security or launch authorization.
