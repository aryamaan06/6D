# Systems and interface contracts

Open http://127.0.0.1:8768/ and choose **Systems & interfaces** in the sidebar. This milestone adds explicit organization, scalar interface comparisons and conservative dependency review to the existing project/revision workflow. It adds no physics adapter or simultaneous coupled solver.

## Use the workspace

1. Select the latest saved revision. Choose **Edit in shared draft**.
2. **Add system** with its name, context, optional parent and model assignments. A model has at most one direct owner; a parent's views include its descendants. Models without an owner remain available in the existing discipline groups.
3. Add another system, then **Add interface**. Choose source and destination systems; select a supplied input or a saved model metric as source; select a supplied destination criterion input. Declare the physical quantity, exact unit, operator, criticality and context.
4. **Apply to shared draft** validates the proposed records with the server. It changes no saved revision. Draft cards produce no numerical verdict.
5. **Save shared revision** preserves the architecture with the project's immutable snapshot. Run supported checks for model-metric evidence. Interface-only edits reuse identical calculator dependencies; the interface comparison is derived separately from the saved results. An input-to-input contract compares supplied declarations and must not be described as calculated or measured validation.
6. Inspect the hierarchy in the sidebar and its relationships on Canvas. Solid lines are declared interface review links; dashed lines show parent/child organization. Parent selection aggregates its model/requirement scope; selecting a child requirement retains its compatible child scope.
7. Edit a source/target record or contract and open **Changes**. The interface section lists connected systems, models and requirements needing review. It traverses the old and new declared relationships, including nested systems and feedback cycles. These are conservative review flags, not predictions of new values or proof of physical coupling.
8. **Report** and the canonical/combined JSON exports include the interface projection with project, revision, run/review, source and projection identities. Print/Save PDF includes expanded provenance. A selected Reader/Inspector view discloses its subset and the project-wide interface count.

The optional [connected example](../examples/connected-systems.project.json) can be imported using **Import project → Project JSON file**. It creates a separate constructed example only when you explicitly import it. Its atmospheric reference is `.5 × 1.2 × 50² × .8 × .25 = 300 N`. It demonstrates model ownership, a supplied thrust allowance and a saved drag allowance without establishing a real spacecraft, force direction or qualified structural limit. No example is inserted into existing projects automatically.

## Meaning of the findings

- **Meets interface criterion:** a supplied/recorded scalar meets the declared comparison in matching literal units.
- **Does not meet interface criterion:** that scalar violates the declared comparison. This is separate from canonical model requirement findings.
- **Not assessed:** missing/currently unavailable model evidence, unsupported metric, incompatible units or another explicit gap prevents comparison. Drafts always remain unassessed.

Source and destination units must equal the contract unit exactly. There is no conversion, inferred sign/direction, coordinate transform, vector transfer, aggregation, tolerance or automatic source-to-target input copying. Equality is exact; a tolerance must be modeled through explicit declared criteria. Criticality is recorded and displayed, without creating a mission-readiness score.

An interface's destination input is a declared comparison value. Merely assigning that input to a destination system does not prove another model consumes it. Only actual existing parameter bindings drive calculator execution. The contract's quantity/conditions and whether the connection is physically appropriate remain user declarations.

Interface review flags do not overwrite scalar test-comparison applicability or original test outcomes. They appear separately beside connected requirement/test evidence. Historical scalar comparisons and their scoped Assistant bundles retain the original baseline; a standalone matching dependency label does not close a separate interface review.

## Record and storage contract

`sixd.project.v1` accepts optional top-level `systems` and `interfaces` lists. They are never injected into older project snapshots. Each system has `id`, `title`, `description`, `parent_id` and `model_ids`. Each interface has `id`, `title`, `description`, `from_system`, `to_system`, `source`, `target_input`, `quantity`, `unit`, `operator` and `critical`. Source is either `{kind:"input",input_id}` or `{kind:"model_metric",model_id,metric}`. Model-metric sources must belong to the source system or its descendants. Input endpoint associations are explicitly declared; unbound budget inputs are allowed.

The bounded record supports up to 64 systems and 128 interfaces. The containment hierarchy must be acyclic; directed interface feedback cycles are permitted and traversal is finite. Duplicate ownership, missing references, unknown fields and invalid scalar/boolean types are rejected. Parent/connected dependencies must be removed or remapped before deletion.

Interface checks are a separate read-only `sixd.system-interfaces.v1` projection. `GET /api/interfaces` reads a saved revision; `POST /api/interfaces/preview` checks a latest-revision draft without saving or calculating. Reads use an explicit SQLite snapshot and source-stability guard. Legacy project and canonical review structures/digests remain intact; architecture lives inside the new saved project snapshots. No new database table is needed.

The canonical verifier's maintained source set remains unchanged in shape. Its source fingerprint changed because project validation now accepts architecture. Existing calculations are preserved as historical evidence; **Run checks** explicitly creates evidence for the current verifier when needed. The application restart also clears a previously connected memory-only key; local organization/checks/reports need no key.

No live inference, model selection or spending-policy change is part of this milestone. This feature does not establish subsystem completeness, calibrated measurements, validated physical coupling, a flight simulation, certification or launch approval.
