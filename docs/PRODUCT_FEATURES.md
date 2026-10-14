# 6D — intended product features

Agreed product direction, updated October 14, 2026 with Arya's simulation/visual-playback request. This is a feature catalogue for planning, not a record of implemented or validated coverage and not a build schedule. The product is called 6D. Build one space-only lifecycle engineering assurance platform; the hackathon submission is a snapshot of the capabilities actually working at its checkpoint.

## Product purpose

Help space teams review proposed designs, investigate engineering problems, compare predictions with tests, and keep conclusions valid as a project changes. Adapt the workflow to the vehicle, mission and evidence supplied. A rocket type, satellite example or Floating Coliseum case is an application of the platform, not a permanent restriction of the product.

## Functional capabilities

1. **Guided project intake.** Accept mission goals, requirements, specifications, supported drawings/CAD, engineering models/code, simulation results and test records. Retain the source and ask for missing information rather than inventing it.
2. **Structured engineering record.** Keep the vehicle, subsystems, interfaces, quantities, units, reference frames, assumptions, environments and operating limits together in reviewed, versioned records.
3. **Requirement-to-evidence tracking.** Connect each requirement and acceptance criterion to the models, calculations, tests and decisions supporting it; make missing verification visible.
4. **Mission-aware coverage.** Determine which checks apply to the mission phase, configuration and environment. Mark unsupported or inapplicable checks explicitly instead of making every project use the same checklist.
5. **Engineering calculation and solver connections.** Run maintained bounded calculations and connect applicable specialist analysis tools. Preserve approximation limits, input mappings, versions and output provenance; a discipline name is not an implemented solver.
6. **Numerical and model credibility review.** Investigate units, numerical convergence, reference agreement and suitable physical constraints; assess applicability and independent validation evidence where available. Passing a numerical check does not establish that a model represents hardware correctly.
7. **AI-guided investigation.** Elicit necessary information, rank possible explanations, select supported discriminating experiments and explain actual evidence. Model-generated prose cannot override acceptance criteria or quantitative findings.
8. **Subsystem interaction review.** Track explicit dependencies and investigate consequences across subsystems. Quantitative interactions require suitable coupled models or evidence; a dependency link alone does not calculate a physical effect.
9. **Scenario, margin and uncertainty analysis.** Review applicable operating conditions, off-nominal cases, parameter sensitivity and engineering margins. Quantified uncertainty needs defensible models and input distributions, not invented failure probabilities.
10. **Design alternatives and proposed corrections.** Suggest changes for engineering review, compare alternatives and rerun relevant checks. Preserve approved requirements and baselines; a proposal is not an automatically accepted design.
11. **Physical-test comparison.** Check data quality and test conditions, connect measurements to the tested configuration and requirements, compare them with predictions, and investigate discrepancies. Any calibration creates a reviewed model revision with separate validation needs.
12. **Revision and evidence impact.** Preserve earlier baselines, flag evidence affected by changes to inputs, models, requirements or assumptions, and identify checks that need repeating.
13. **Operational evidence review.** Connect supported telemetry and mission events to the operating configuration; investigate anomalies and implications for earlier models and requirements. This does not imply autonomous control of flight hardware.
14. **Findings, explanations and reproducible reports.** Show calculations, plots, evidence sources and reproduction details. Distinguish requirement violations, numerical defects, method limitations, model applicability and unresolved questions. Keep assessment coverage visible.
15. **Readiness recommendations.** Support positive or negative recommendations when an agreed review's evidence permits them. Identify unresolved blocking requirements, residual risks and approval status. Design review and launch-readiness review require different evidence; recommendations do not confer launch authorization or guarantee success.
16. **Team review and governance.** Shared projects, assigned responsibilities, review discussions, decisions, approvals, permissions and audit history.
17. **Secure execution, integrations and spending control.** Protect engineering data; control tool and model access; isolate permitted code execution; connect supported CAD/CAE, mission-analysis, requirements, source-control, laboratory and telemetry systems. Record inference/compute usage and enforce approved budgets.
18. **Coherent product experience.** A calm workspace with clear navigation, understandable summaries, evidence on demand and usable incomplete/error states. Apple's presentation and Notion's organization guide the design; UI specifications precede implementation.
19. **Simulation and visual playback.** Run supported physics models or import traceable specialist-solver results, then show predicted behavior through synchronized plots and appropriate 2D/3D playback. Tie each run to the exact project revision, inputs, conditions, model/solver versions and evidence. Allow baseline/revision and supported scenario comparisons; make failed or unresolved behavior inspectable too. Simulation can supply evidence during review and be replayed after a positive assessment. Geometry and motion must have stated sources; illustrative animation is labelled separately and cannot support engineering findings. A visual prediction is conditional on its model and inputs, not a guarantee of real-world behavior. See SIMULATION_PLAYBACK.md for the feature specification.

## Intended engineering coverage

All areas below remain in the full product development plan. Coverage is implemented and validated progressively through native bounded tools and applicable specialist integrations, not a promise that every field is already supported or that 6D must write every solver itself.

| Area | Relevant topics |
| --- | --- |
| Mission and flight dynamics | Trajectories, orbit, transfers, rendezvous, entry, descent, landing and arrival/capture, as applicable |
| Propulsion and fluid systems | Performance, propellant budgets, tanks, feed systems, thrust, burns, throttling, restart and thermal interfaces |
| Structures, materials and mechanisms | Loads, stress, deformation, buckling, vibration, fatigue, joints, separation, deployment and landing loads |
| Aerodynamics and aerothermodynamics | Atmospheric forces/moments, stability, heating and flow-regime applicability |
| Thermal systems | Heat sources, transport, rejection, temperature limits, transients and thermal protection |
| GNC | Guidance, navigation, estimation, control, sensors, actuators, pointing and relative-motion behavior |
| Power, electromagnetics and electronics | Generation, storage, distribution, electromagnetic interactions, component limits and relevant qualification evidence |
| Avionics, flight software and communications | Interfaces, timing, fault handling, software assurance, telemetry and communications evidence from supported specialist systems |
| Assembly and space infrastructure | Alignment, robotic assembly, docking/capture, deployment, inspection and infrastructure operation |
| Environment, reliability and system integration | Relevant pressure, radiation, temperature, weather, debris and other load cases; failure modes, redundancy, ground interfaces and coupled behavior |

Crew life support, particular recovery systems and other specialized functions enter the applicable review when the project requires them. Floating Coliseum additionally brings electromagnetic acceleration, structural/thermal coupling, momentum management and destination-delivery requirements into focus. Previously supplied Coliseum numbers remain illustrative, not engineering requirements.

## Current implementation boundary

Implementation resumed October 14. The demonstrated backend now includes structured project/requirement records, four bounded engineering formula adapters, evidence receipts and revision comparison through explicit dependencies, plus curated circular-orbit numerical checks and offline tool orchestration. All 115 integrated development tests passed. The new project workflow is currently CLI; the existing browser remains the orbital prototype. The live provider is configured without a key but actual inference has not been demonstrated. Interactive simulation playback is now explicit in the plan but is not implemented. Higher-fidelity/coupled solvers, broader ingestion, physical-test/operational integrations, collaboration and public deployment remain unimplemented. This catalogue remains the full product objective; docs/BUILD_PLAN.md and docs/SCREEN_SPEC.md govern the next work.
