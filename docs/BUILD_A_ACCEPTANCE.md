# Build A: integrated rocket reference

Authorized October 24, 2026. A founder or reviewer must be able to create one constructed rocket review, calculate a baseline, reduce thrust, inspect affected dependencies, save and recalculate, then restore thrust and compare the retained evidence. No API key or hand-written JSON is required.

Acceptance criteria:

1. One visible reference entry creates a new project through the existing intake controls. Five supported calculations appear together: ideal propulsion, vertical flight, atmospheric load screening, static structure and independent steady thermal. Existing projects are preserved; opening the app does not create or run this reference.
2. Shared mass, thrust and specific impulse inputs feed propulsion and flight. Explicit one-way scalar links connect maximum sampled flight speed to a separate reference-density drag screen, then to a declared transverse cantilever load. These are separate screening cases, with no simultaneous physics or feedback claimed.
3. The 20,000 N baseline has nine supported criteria met and one launch-guidance requirement unassessed. Reducing only thrust to 11,000 N makes the 5,000 m **burnout-altitude** criterion unmet. Restoring 20,000 N restores the supported criteria without erasing the failure receipt or resolving guidance.
4. Each edit previews dependencies before saving. Recalculation updates four supported models and reuses the unchanged thermal result with its original provenance. Historical, stale, unsaved or customized configurations cannot accidentally receive the canned next edit.
5. Actual saved results drive the review, linked-calculation view, flight playback, comparison and report. Independent closed-form component checks and a complete browser journey verify the reference. Numerical support gaps propagate to linked calculations instead of supplying a pass.

Scope: constructed inputs and limits; ideal delta-v budgeting; one-dimensional constant-thrust flight in an exponential atmosphere; supplied aerodynamic coefficients; a static beam fixture; a steady radiator. The ideal required-burn duration is different from full-propellant flight burnout. The load screen is not flight maximum drag. Thermal is not ascent aeroheating. Guidance, navigation, stability, staging, reentry, landing and whole-rocket structural or thermal validity remain unassessed. Builds B and C supply their separately agreed extensions later.

No live inference, paid comparison, deployment or model activation is part of A.
