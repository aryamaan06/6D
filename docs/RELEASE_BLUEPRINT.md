# 6D — October 21 submission blueprint

Planning revision: October 13, 2026. Application implementation has not resumed under this blueprint. Owner: Arya; implementation lead: Codex in the original chat titled 6D.

Strategic update from the October 13 voice conversation: the primary objective is now the full future 6D startup platform, beginning with an expandable shared foundation. October 21 is a hackathon checkpoint whose package contains only working, validated capabilities. The bounded models and gates below remain useful initial implementation specifications, not a ceiling on development or a claim that the full platform will be complete at the checkpoint. Broader capabilities need their own specifications and validation; no application changes or paid model calls were made by this planning update.

## Product decision

Arya requested orbital verification, propulsion, structures and thermal checks in the submission target. Include all four as bounded, connected engineering screening capabilities. A proposed capability is not implemented or validated merely because it appears here. The demonstrated release must label unfinished or unsupported work honestly. Whole-spacecraft reliability, hardware qualification and flight certification are not supported conclusions.

October 13 decision: retain these four as the core thruster-change review. Add a bounded aerodynamic load adapter for explicitly relevant atmospheric inputs. It is conditional on the declared mission phase and model applicability, rather than a mandatory check in an ideal vacuum-orbit example. Full GNC simulation, avionics/embedded flight-software verification and prediction of aerodynamic heating remain outside this release. Track relevant GNC assumptions and flag GNC review required after changes that affect them.

One journey: a satellite team changes a thruster or maneuver configuration and reviews which engineering claims still have applicable evidence. Review requirements and assumptions, compute supported checks, inspect consequences, renew affected evidence and export a versioned review.

The first mission pack is a constructed, clearly labelled example. Example dimensions and performance values are adjustable illustrations, not a real spacecraft design or fixed product requirements. Seek an independently sourced reference case and relevant user feedback without mislabelling synthetic data as customer evidence.

## Bounded domain capabilities

| Domain | Submission target | Required boundary |
| --- | --- | --- |
| Orbit | Repair existing planar circular point-mass verification; add a separately verified analytic circular-to-circular impulsive maneuver budget if applicable to the demonstration. | The current circular propagation does not verify a transfer trajectory. Distinguish reference-orbit checks, analytic budget and maneuver applicability. |
| Propulsion | Ideal propellant requirement, mass consistency, mass-flow and burn-duration estimates under declared thrust and specific impulse. | Constant-parameter ideal model; excluded losses stated. Long finite burns cannot be treated as validated impulsive trajectories. |
| Structures | Stress and deflection of a declared simple, linear-elastic mounting-beam model under a specified static load and boundary conditions, compared with stated allowables. | No general CAD/FEA, joints, vibration, fatigue, launch-load qualification or structural certification. Do not size a part from a formula and call that overall feasibility. |
| Thermal | Declared sustained heat input versus radiative rejection at an allowable temperature; simplified lumped steady-state equilibrium where the model applies. | Explicit heat paths and environmental assumptions. Electrical power is not automatically heat transferred to the spacecraft. A steady-state result is not a prediction of peak temperature during a short burn. |
| Aerodynamic loads (conditional) | Dynamic pressure and drag-load estimates from supplied atmospheric conditions, relative speed, declared reference area and applicable drag data; compare with stated limits. | No CFD, determination of coefficients from geometry, complete aerodynamic stability analysis or ascent/reentry trajectory prediction. Coefficient source, reference-area convention and flow-regime applicability are required. Unsupported data abstains; an explicitly out-of-scope atmospheric phase is labelled not assessed. |

The thermal adapter does not verify aerothermodynamic heating. If it accepts a separately supplied heating load, record its source and distinguish the thermal response calculation from verification of that heating load. Add a clearly labelled atmospheric-input example for the aerodynamic adapter only once independently checked. Do not imply the primary vacuum-orbit example demonstrates atmospheric analysis.

Inputs must preserve units, frames where relevant, model applicability, requirement limits, materials, load conditions, source provenance and revision. Missing data produces questions or an unresolved result, not invented defaults. Local Python adapters initially execute explicitly trusted supported code; the hosted demonstration uses controlled inputs rather than arbitrary uploaded execution.

## Coupling and evidence

- Orbit requirement and declared maneuver assumptions -> required ideal velocity change -> propellant and burn-duration estimates -> applicability of the maneuver approximation.
- Thruster/configuration mass -> vehicle mass -> propellant demand.
- Declared thrust and mounting geometry/load direction -> static mounting-beam stress and deflection.
- Declared heat transferred to the spacecraft, radiator properties and environmental assumptions -> thermal estimate and margin.
- Applicable atmospheric conditions, reference area and drag data -> dynamic pressure/drag estimate and its stated requirement margin. Any transfer of these loads to a structural model requires an explicit compatible load-case mapping; do not simply add unrelated forces.
- Delivered impulse direction, thrust alignment, pointing and execution timing are maneuver assumptions. Changes affecting these, mass/inertia, actuator capability or control behavior -> GNC review required. This is a coverage/dependency flag, not verified controller behavior or simulated flight readiness.

Store reviewed dependency links. A changed input, assumption, requirement or model version marks affected evidence as needing reconsideration; unchanged evidence remains explicitly tied to its original applicability. An unaffected numerical result does not imply the entire spacecraft is unaffected. Reruns create new records and preserve old ones.

Nemotron can inspect supported revisions, elicit missing inputs, propose links for review, select bounded follow-up checks and explain actual evidence. Maintained deterministic models and acceptance policies supply quantitative results and numerical findings. Explanations cite real evidence IDs. Keep AI investigation completion, check outcomes and overall supported-review completeness separate. An AI failure must not overwrite valid completed numerical evidence or appear as a completed AI review.

Also distinguish numerical implementation defects from engineering requirement violations. A correctly computed thermal estimate outside a declared limit is a requirement failure under that model, not automatically a software bug or a prediction of hardware failure. Record model applicability, numerical-check status, requirement status and investigation completion separately.

## Demonstration and acceptance

Show a supported baseline, a revised configuration with a consequential tradeoff, selectively stale evidence, a relevant agent-selected follow-up, and renewed evidence after a correction. Also show a numerical-method decoy and a missing-input/inapplicable-model case.

Each domain needs independently worked reference values, limiting/scaling cases, invalid-input cases and seeded counterexamples. Report provenance and construction method. Do not call an AI-generated fixture human-authored or a rehearsal a blinded benchmark.

Repair the observed force-probe blind spot and overconfident fault attribution. Check supported method properties rather than treating numerical order as algorithm identity. Make failed/incomplete investigations prominent. Document evidence IDs in tool results and test their use; do not assume tool names and evidence IDs must be identical.

Compare the useful agent workflow with a declared execution-enabled agent and deterministic baseline. Measure relevant-check selection, unsupported conclusions, defects, false accusations, completion, time and cost as appropriate. Publish results including losses; make no superiority claim before measurement.

## Product experience

Design direction: Apple-like presentation and polish with Notion-like organization and inspectable records. Define flow, wording, visual hierarchy and failure states before UI implementation.

Screens: project overview; model/requirements and assumption review; investigation; evidence review; revision comparison; exportable report. Use a quiet workspace, legible plots, clear applicability labels, concise summaries and technical detail on demand. New/stale/unresolved/failed states must be distinguishable. Do not use an unsupported overall safety score.

## Build sequence and gates

| Target dates (Asia/Calcutta) | Work | Acceptance |
| --- | --- | --- |
| Oct 11–12 | Finalize mission-pack/schema, evidence policies, screen specification; repair verifier; prepare local configuration and obtain the first live Nemotron receipt after planning is complete. | Counterexamples are handled correctly; provider run has real completed calls and actual tool evidence. |
| Oct 12–14 | Build and independently check the four bounded adapters and shared inputs. | Supported reference, limiting and invalid cases have truthful outcomes in each domain. |
| Oct 14–16 | Connect revision dependencies, evidence renewal and meaningful bounded agent follow-ups. | A change invalidates relevant evidence; a rerun creates a new version; missing/inapplicable inputs abstain. |
| Oct 15–17 | Implement approved interface and complete the user journey. | A fresh user can supply supported input, review assumptions, inspect findings and compare a revision. |
| Oct 17–18 | Run evaluation and relevant-user review where obtainable; freeze feature scope. | Measured results and limitations are recorded; AI value is assessed without manufactured claims. |
| Oct 19–20 | Deployment, clean setup, repository/license package, feedback, description and video rehearsal. | Concrete hosted/repository package is reviewed; runtime and source/evidence versions agree. |
| Oct 21 | Submission-ready checkpoint. | Strongest complete truthful release; all advertised capabilities work within their stated coverage. |

These are planning targets, not proof that all capabilities will pass their acceptance gates. Cut generalization, extra orbit families, automatic patching, broad document/CAD ingestion and enterprise account features before weakening the supported workflow. Keep planned four-domain work in the roadmap; clearly identify any unfinished capability in the submitted material.

The original October 11–12 targets are historical planning targets and have not been met by implementation under this blueprint. As of October 13, the additional adapters and live inference remain unimplemented/untested. Rebase the execution schedule when implementation resumes; do not describe these milestones as complete.

## Founder tasks and tool allocation

Arya: keep the existing workspace open, enter the active key only in a private local terminal using the prepared configuration, review product language/screens, help request relevant user feedback using a prepared request, and record the final public demo. Codex: specifications, architecture, implementation, independent checks, integration, deployment preparation and release acceptance. Antigravity: bounded read-only or isolated review assignments; no simultaneous competing rewrites.

Arya has no known engineering reviewer and requested help finding one. Prepare a shortlist and respectful, specific review request. Public communities are places to seek candidates, not evidence that a qualified reviewer has agreed. No outreach messages have been authorized or sent.

## Account and spending status

Arya revoked the exposed key and privately created `6d-local-development`. Screenshots show a $29.50 account balance and separate $1 trial credit with eight days remaining; the trial expiry does not establish the expiry of the $29.50 balance. Initial model selection: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` at `https://api.tokenfactory.nebius.com/v1/`, with displayed approximate prices $0.06 input/$0.24 output per million tokens. Verify the actual applicable price ceilings and license before enabling a live run.

User explicitly approved a cumulative $5 initial live inference allowance from existing balance only, with no additional card spending. Their selected continue-paid-usage preference permits provider card charges if the balance becomes negative; this is not authorization for us to create those charges. The adapter allowance covers our adapter, not unrelated account activity. Never store or print the key. No paid calls during planning. Hosting access/credits, ongoing judging-period availability and any additional costs remain to be resolved against a concrete package.

## References

- NASA requirements verification and validation planning: https://www.nasa.gov/reference/system-engineering-handbook-appendix/
- NASA ideal rocket equation: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/
- NASA specific impulse: https://www.grc.nasa.gov/www/k-12/airplane/specimp.html
- NASA small-spacecraft thermal control: https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/
- NASA drag equation and reference-area conventions: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/
- NASA integrated avionics/GNC and atmospheric testing examples: https://www.nasa.gov/reference/testing/
- Independent reference-tool candidate, not an implemented integration: https://github.com/NASA/GMAT
- Candidate reviewer community: https://community.libre.space/

These references do not establish NASA endorsement, compliance or certification of 6D.
