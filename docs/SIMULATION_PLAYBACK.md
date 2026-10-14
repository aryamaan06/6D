# 6D — simulation and visual playback

Product feature requested by Arya on October 14, 2026. Planned, not implemented. The full startup platform remains the objective; the hackathon receives a tested snapshot of working capabilities.

## User purpose

An engineer should be able to inspect how a design is predicted to behave under specified conditions, understand where a requirement fails, and compare a changed configuration or supported scenario. A positive design assessment may lead into a replay, but simulations also belong within the assessment and can expose a failure before approval. Failed/incomplete reviews can contain useful supported simulation results.

For a rocket, eventual applicable outputs could show its trajectory and supported histories such as speed, propellant, control response, loads or temperatures. For a satellite, relevant outputs differ; an orbital-infrastructure project uses its own applicable models. These are coverage goals, not existing capabilities or a claim that one current solver computes everything.

## Minimum product requirements

1. **Computed behavior.** Quantitative plots and motion come from a supported physics model or traceable external solver result. A language model coordinates the run and explains evidence; it does not invent motion, temperatures or failure probabilities.
2. **Run identity.** Preserve the exact project revision, reviewed inputs, conditions, units, reference frames, time base, model/solver versions, source fingerprints and result provenance. Replays never silently adopt changed inputs. Display simplified or supplied geometry with its source stated; a realistic-looking model alone establishes no physical fidelity.
3. **Understandable playback.** Provide time controls and synchronized quantities where data exist, with evidence/requirement links and scope visible. Choose 2D or 3D according to the supported data and review question. Warn about unsupported display channels through plain coverage states, not invented values.
4. **Comparison and scenarios.** Compare baseline/revised designs and explicit supported conditions. Each changed scenario creates a separate run. Physical coupling and uncertainty displays require suitable models/data; a dependency graph or animation alone does not establish them. Preserve unmet/unresolved requirements and model limits while comparing.
5. **Evidence integrity.** Verify displayed samples, units, transforms and interpolation against stored results; check the underlying model with independent references appropriate to its purpose. An illustrative animation is labelled and excluded from engineering findings. Simulation predictions remain conditional on models, inputs and conditions.

## Initial implementation candidate

Start with recorded trajectory/time-history playback for the already-supported planar orbital family, after defining and independently verifying the state-history export. Reuse contract/source/evidence identity and compare compatible runs. This is a development entry point, not a permanent product restriction or a whole-spacecraft simulation.

The four current design formula adapters produce bounded scalar metrics, not dynamic time histories. Showing their values or a static diagram does not implement launch/landing, temperature-transient or full structural simulation. Broader playback expands alongside validated dynamic models and specialist integrations.

## Acceptance gate

A reviewer can identify the simulated configuration and conditions, connect displayed behavior to actual stored results, inspect supported failures/gaps, and distinguish a computed prediction from illustrative presentation. Replaying or comparing data must not alter the original evidence or its conclusions. Only coverage that passes its model and display checks may be included in the submission.

Model/simulation credibility and project-specific acceptance criteria are also treated in [NASA-STD-7009](https://standards.nasa.gov/standard/NASA/NASA-STD-7009), checked October 14. This is a relevant reference, not a claim that 6D complies with or is certified under that standard.
