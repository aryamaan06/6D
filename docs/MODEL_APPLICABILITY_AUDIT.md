# Applicability audit for the seven bounded models

Published-reference checks establish agreement for specified idealizations and inputs. They do not establish every assumption for a user's design. The current interface already retains model assumptions and explicit not-assessed lists in Inspector/Reader/Report. The distinction below records what that evidence can support.

October 19 safeguard increment: new orbital adapter v2 reviews now require explicit position/velocity tolerances and three-grid evidence before numerical criteria can be assessed. Missing evidence, excessive grid disagreement and allowance-overlapping criteria stay unresolved in canonical findings and downstream scalar use. New results freeze bounded reference/applicability context; historical v1 findings are preserved with an accuracy-not-assessed notice. See [accuracy safeguards](ACCURACY_SAFEGUARDS.md). This enforces a numerical evidence policy, not general physical applicability or a rigorous true-error bound.

| Model | Enforced numerical/input gates | Physical assumptions requiring external evidence |
| --- | --- | --- |
| Ideal propulsion | Positive masses/Isp/thrust; dry mass no greater than initial mass; nonnegative prescribed delta-v; finite outputs | Effective Isp/thrust applicability, reserves, flight losses, staging, feed systems and real engine performance |
| Cantilever | Positive length/stiffness/section geometry; nonnegative tip-force magnitude; finite outputs | Small-deflection slender-beam regime, load direction/location, actual boundary conditions, material allowable and section validity |
| Radiative equilibrium | Positive area/emissivity; emissivity no greater than one; nonnegative heat/background temperature | Unit view factor, grey/isothermal surface, black environment, equilibrium, absence of other heat paths, correct supplied loads |
| Drag | Positive reference area; nonnegative density/speed/Cd; finite outputs | Cd for the selected reference area/attitude/Mach/Reynolds regime, atmospheric condition, force direction and distributed loads |
| Two-body orbit | Bounded elliptic domain, eccentricity/clearance/window/step policies, finite resolved states; eight-period boundary now permits only 16 ULPs of roundoff | Appropriate force model, inertial frame, ephemerides, perturbations, between-sample limits and an engineering-adequate numerical error budget |
| Power/energy | Nonnegative capacities/loads/generation, positive mode durations, whole equipment counts, bounded modes/loads and finite representable timelines | Measured bus loads, usable battery derating/reserves/losses, solar geometry, recharge/SOC, transients and qualification |
| Single-axis control | Positive inertia/duration/numerical tolerances, nonnegative gains/torque capacity, bounded state/grid, refinement agreement | Appropriate inertia/feedback/actuator model, uncertainty, sensors/delays, nonlinear switching accuracy and real spacecraft behavior |

## Warnings and gaps identified

- A mathematically completed beam calculation can still be outside small-deflection theory. Current inputs do not establish geometry/material/constraint applicability. No arbitrary deflection-ratio threshold is invented by this benchmark.
- Supplied drag coefficients are not validated by the single-condition equation. Current inputs do not carry enough Mach/Reynolds/attitude evidence for that decision.
- Steady thermal agreement does not establish equilibrium or unit view factor for a spacecraft.
- Orbital grid/clearance guards are not mission accuracy guarantees. External SPICE comparisons show kilometre-scale accumulated position differences on some long or eccentric runs even at the current step ceiling. Requirement interpretation needs an explicit numerical accuracy/uncertainty budget; a passing broad regression tolerance is not such a budget.
- Control coarse/fine agreement is a numerical diagnostic rather than a certified error bound. Published linear solutions and continuously clipped torque are covered here; general clipping/release transitions remain a reference gap.
- Power budget completion does not establish battery adequacy under charging, degradation or transient loads. Energy and power margins must remain separate.

These physical applicability questions remain explicitly unassessed and visible during intake and review. The new orbital policy enforces user-declared numerical grid-agreement allowances; it does not supply missing physical criteria or certify the user's system.
