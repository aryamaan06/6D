# Orbital numerical verification scope — October 14, 2026

## Supported statement

The verifier checks exposed, curated acceleration and stepping functions under a declared planar point-mass circular-orbit contract. Initial conditions are derived from that contract. It compares them with an exact analytic circular solution, not another numerical solver. This establishes findings about the supported software behaviour, not the physical validity of the model or any spacecraft.

No arbitrary code is accepted. The numerical checks themselves require no model inference. A replaceable structured provider can coordinate the supported checks without authority to change evidence or verdicts; offline fixture orchestration is verified, while live Token Factory compatibility remains untested. Kernel summaries are fixed and evidence-linked. The newer bounded design-adapter/project-review workflow has its separate scope in FOUNDATION_BUILD.md.

## Experiments

1. **Central-force reference:** 72 probes spanning axes and quadrants, three radii and three gravitational-parameter scales. Compare acceleration components with the declared central-force expectation. Maximum relative residual must be at most `1e-10`, a predeclared conservative floating-point comparison threshold. It is not a physical uncertainty bound.
2. **Circular reference and refinement:** one period with 512, 1024, 2048 and 4096 steps. At every step, measure combined position/velocity error, normalized by radius and circular speed, against the exact solution. Estimate order as the base-two logarithm of coarse/fine maximum errors.
3. **Rotated initial conditions:** repeat the finest two levels in two additional phases. The finest-level estimates must be within `0.20` of the declared order, and errors must decrease on refinement. This tolerance is an explicit prototype engineering policy; it is not a theorem, a confidence interval or a universal threshold.
4. **Declared Verlet reversibility:** run forward then backward over a quarter orbit at 128, 256 and 512 steps for three phases. Compare return-state error against the predeclared floating-point allowance `128 * machine_epsilon * (2 * steps + 1)`. This is an engineering comparison policy, not a rigorous error bound. It catches the reproduced nonsymmetric second-order RK2 mismatch; it does not prove the exact algorithm's identity. This check does not apply to the correctly declared Euler fixture.

Very small errors below the declared comparison floor produce an inconclusive estimate. Unsupported or ambiguous contracts abstain before executing numerical experiments. Experiment execution failures are recorded as inconclusive, not silently interpreted as physical defects.

Energy change is recorded for context. Velocity Verlet is not claimed to conserve exact mechanical energy. The correctly declared Euler fixture has first-order convergence and observed drift consistent with a method that does not conserve energy in this case. It is used to exercise the method-limitation outcome. These demonstrations do not establish false-accusation rates on general software.

## Evidence records

- Contract digest fixed before experiments, reviewed source function digests, verifier-source digests and runtime version.
- Raw probes, refinement measurements, rotated-condition estimates, outcomes and mandatory exclusions.
- UTC creation time, deterministic audit identity, report-content digest, reproducible JSON and portable HTML.
- Append-only application writes with separate filenames for later snapshots.

Hashes detect accidental changes when checked against the stored digest. They are not signatures or authenticated proof: somebody able to rewrite a record and its digest can forge both. Local acknowledgements do not establish authenticated identity. Reproduction requires the recorded contract and matching source versions; any changed version must be treated as a new evaluation.

## Findings

- `defect_likely`: contradiction with a supported declared force, order or applicable reversibility expectation. Refinement failures do not uniquely localize the faulty function.
- `method_limitation`: supported behaviour is consistent with the correctly declared Euler fixture and its limitations.
- `no_defect_found_in_scope`: no supported defect found; no overall correctness conclusion.
- `inconclusive`: contract ambiguity, unsupported scope, unresolved comparison or experiment failure.

## Deliberately excluded

Real-world model validity, eccentric orbits, burns, transfers, rendezvous, capture, landing, perturbations, unit inference, frame conversion, customer repositories, long-duration behaviour, arbitrary uploaded execution, hardware qualification, guarded patching, AI diagnosis, commercial demand and comparative performance.

NASA-STD-7009 discusses model/simulation credibility and project-defined acceptance practices. This prototype is informed by that distinction and makes no compliance claim: https://standards.nasa.gov/standard/NASA/NASA-STD-7009 (checked October 10, 2026).
