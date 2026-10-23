# Powered vertical flight acceptance

Authorized build, October 22, 2026. A user creates the constructed reference,
runs it, inspects saved altitude/velocity/mass/forces through burnout and coast,
changes thrust in a draft, saves a revision, reruns affected checks and exports
the evidence. These operations must preserve earlier records.

Acceptance gates:

1. Constant thrust/Isp, analytical mass depletion, inverse-square gravity and
   signed drag in a declared exponential atmosphere. Burnout is an exact segment
   boundary with separate pre/post-cutoff samples. No staging, steering or landing.
2. Vacuum analytical velocity/altitude; independent adaptive integration for
   constructed atmospheric cases; coast energy and mass conservation checks.
3. Three retained RK4 grids. Failure of declared grid agreement leaves diagnostic
   playback available but blocks requirement satisfaction and downstream scalar
   use. A criterion overlapping its numerical allowance remains unassessed.
4. Saved artifacts retain inputs, solver identity, samples, grid comparisons,
   assumptions and exclusions. Tampered metrics/samples/diagnostics are rejected.
   Historical verification checks consistency without rerunning the ODE.
5. Existing authoring, revision invalidation, targeted reuse, scenarios, chains,
   Assistant evidence, reports and coverage accept the new model without changing
   prior results. Old source manifests remain verifiable.
6. Browser checks cover empty state, reference creation, calculation, playback,
   cutoff, draft suppression, revision rerun and report. Existing founder data,
   configurations and spending records remain unchanged. No paid calls required.

Grid agreement is not a rigorous error bound or proof of physical applicability.
Extrema are sampled extrema. Reference cases are constructed, not flight data.

Delivery qualification, October 23: the first main-app opening exposed the older
default-project automatic rerun behavior and appended one local run. The original
twelve runs remain byte-identical; the extra record is preserved. Startup has
been corrected so existing projects require explicit reruns, and final checks
confirmed no further append. See POWERED_FLIGHT_RESULTS.md for the full outcome.
