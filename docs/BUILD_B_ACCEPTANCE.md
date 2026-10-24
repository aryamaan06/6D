# Build B: bounded planar ascent with prescribed steering

Authorized October 24, 2026 using Sol 6.1 Ultra. A reviewer must be able to load an integrated rocket reference with a supplied pitch schedule, calculate a saved trajectory, play its horizontal and vertical motion, change the schedule and inspect updated requirements and dependencies. No live key is required.

Acceptance:

1. Preserve the existing vertical-flight adapter, Build A example, original projects, immutable receipts and spending ledger. Add a distinct bounded `guided_ascent` adapter and a loadable integrated reference; ordinary form/table authoring supports its inputs.
2. Integrate a point mass in a nonrotating body-centered inertial plane. Initial position is (launch radius, 0), velocity is zero. Gravity is central inverse-square; supplied exponential atmosphere is stationary; drag opposes the full velocity vector. Constant thrust follows a declared local-vertical pitch programme. This is prescribed steering, not closed-loop launch GNC.
3. State the angle convention, SI units, frame, atmosphere and domain. Mass depletion is analytical. Segment RK4 at both pitch-schedule boundaries and burnout, pin endpoints, and retain three aligned grids. Continuity, mass exhaustion, thrust cutoff and event sides must be checked. Reject unsupported initial liftoff, domain exits and unresolvable schedules.
4. Saved results feed requirements, one-way scalar links, targeted recalculation, full review/export and playback. Grid gaps and allowances overlapping criteria leave findings unassessed; missing accuracy cannot feed a downstream pass. Edits never reuse a stale flight response as current evidence.
5. The flight tool distinguishes vertical and planar-steering modes. Playback shows saved downrange and altitude, steering, mass and loads, with axes, scrubber, keyboard and exact burnout sides. Draft, loading, unavailable and historical contexts are explicit; no browser physics is performed.
6. Check vertical reduction, analytic vacuum motion, mirrored steering, drag direction, event handling and receipt tampering. Separately written SciPy DOP853 equations compare constructed tilted cases, integrating mass as a state. This is a numerical cross-check, not physical or human validation. Verify the complete browser path and affected existing regressions.

Scope remains point-mass planar ascent and above-surface coast with constant engine performance, supplied coefficients and a simple atmosphere. No Earth rotation, lift, six-degree-of-freedom attitude, closed-loop tracking, throttle scheduling, staging, aeroheating, entry or landing. Variable thrust and staging remain Build C. No AI or external-service spending is part of B.
