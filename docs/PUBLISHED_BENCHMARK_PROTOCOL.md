# Published-reference engineering benchmark protocol

## Acceptance

Each of the seven currently maintained engineering models must have at least one recorded comparison with a published numerical example, an independently evaluated published analytical solution, or an established external implementation. Both the source and the mapping from that source to 6D's bounded model must be explicit. A source-equation calculation with constructed inputs is labelled as such; it is not relabelled as a published worked numerical example or measured hardware data.

Record supplied inputs, units, source URLs/sections, reference method, expected and actual outputs, numerical tolerances, errors and pass/fail for each check. Declare tolerances before interpreting results. Do not round differences away, alter physical inputs to get a pass or silently fall back from an unavailable external reference tool. A failed check or missing reference remains visible.

Use the public maintained engineering adapter for actual results. Reference functions must not call the production solver or import its constants/metrics to construct their expected values. Published rounded values get source-precision tolerances; higher-precision analytical cases use explicit floating-point allowances. Numerical orbit/control checks compare retained states, not merely conserved energy or the implementation's own grid-agreement diagnostic.

## Current scope

- Ideal propulsion: ideal rocket/exhaust-speed relations only; no engine performance, staging, gravity/drag losses or propulsion-system qualification.
- Structures: uniform linear Euler–Bernoulli cantilever, rigid clamp and transverse free-end force; no buckling, fatigue, dynamics, shear or load-case validation.
- Thermal: one isothermal grey surface with an isothermal black background and unit view factor at equilibrium; no transient, conduction or spacecraft thermal qualification.
- Drag: a supplied single-condition density, relative speed, coefficient and reference area; no aerodynamic coefficient prediction or atmospheric trajectory.
- Orbit: unforced point-mass two-body states in one inertial frame over bounded elliptic intervals; no perturbations, thrust or launch/landing.
- Power: supplied bus loads/generation and usable battery energy accounting; no battery chemistry, recharge, state of charge or independently qualified equipment.
- Attitude: one rigid axis, ideal PD feedback/torque source and supplied constant disturbance; no navigation, three-axis motion or full vehicle GNC.

Run explicit domain-rejection checks alongside numerical benchmarks. Distinguish enforced parameter/numerical bounds from physical assumptions that current inputs cannot prove. This milestone documents those gaps; absent evidence is not replaced by a claim of physical validity.

## Independence and limitations

Published sources and an external propagator strengthen implementation verification beyond self-consistency tests. Source-to-model mappings, reference code and tolerances are still assembled by AI and require human engineering review. Passing these finite cases does not validate arbitrary geometries, environments, customer data or a complete mission. Real physical validation, model uncertainty and independent expert approval remain separate work.

External dependencies are development-only and pinned. No customer data or credentials are sent to reference tools. No paid Nebius inference, provider changes or broader solver capability is needed for these benchmarks.
