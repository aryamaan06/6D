# External-reference checks: single-axis attitude control

Reviewed and run October 19, 2026. These are numerical checks of the declared mathematical model, not independent physical validation or a spacecraft qualification.

`tools/published_control_benchmarks.py` exports `run_checks()`. Expected values use elementary closed forms and their derivatives, separately from the production integrator. Every saved angle, signed error, rate, requested torque and applied torque is compared. Selected samples and maximum discrepancies are retained in each receipt. The five cases require only Python's standard library and the production code under test; there is no network or inference call during reproduction.

## Primary references and mapping

1. [MIT 18.03SC, Practice Problems 10 solutions](https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/79f2349d10404454ea6ed6f959fc1d33_MIT18_03SCF11_rec_08s13_sol.pdf), Q2, pages 1–2: the published solution is `x=exp(-t/2)*cos(3t)` with `m=1`, `b=1`, `k=37/4`. Q5, page 3: `x=(2+5t)*exp(-t)` for `x(0)=2`, `x'(0)=3`, and `m=1,b=2,k=1`. These are **published worked solutions**, mapped from displacement to angle about a fixed rigid axis; `m,b,k` become `I,kd,kp`. Both targets are zero. Rate is the independently differentiated published function; signed error is target minus angle.

2. [MIT RES.8-009, Lecture 4: Damped Oscillations](https://ocw.mit.edu/courses/res-8-009-introduction-to-oscillations-and-waves-summer-2017/mitres_8_009su17_lec4.pdf), equations 4, 8, 11, 14 and 15, pages 3–5, gives the characteristic-root forms. Two additional cases are **constructed from those published equations**, not published numerical spacecraft examples: overdamping at `I=2,kp=4,kd=6`, and an underdamped constant-disturbance case at `I=2,kp=8,kd=4,d=.2`. For the latter, shift angle by the equilibrium `target+d/kp` before solving the homogeneous equation.

3. [MIT 8.01SC rotational-dynamics lecture transcript](https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/f50ece7a5a7980dc9d24fe8376a9978c_X9K8LT7SCZ0.pdf), pages 2–4, relates torque, inertia and angular acceleration. The fifth case is **constructed constant clipped torque**: `I=10`, actuator `.1 N*m`, no disturbance, initially at rest, so `angle=.005t²`, `rate=.01t` over `0..1 s`. Its command `2-.01t²-.01t` is at least `1.98 N*m`; it therefore stays above the actuator limit throughout this interval.

## Recorded results

All five cases passed. Absolute acceptance thresholds, declared before comparison, are `1e-8 rad` for angle/error, `1e-8 rad/s` for rate, and `1e-7 N*m` for torque. Sample count and the sampled saturation fraction must match exactly. These thresholds are numerical comparison criteria, not hardware tolerances.

| Case | Reference kind | Maximum angle discrepancy, rad | Maximum rate discrepancy, rad/s |
| --- | --- | ---: | ---: |
| MIT underdamped | Published worked solution | 3.67234e-10 | 1.12367e-9 |
| MIT critical | Published worked solution | 6.75047e-11 | 8.52893e-11 |
| Overdamped | Constructed from published equation | 2.25021e-12 | 5.05282e-12 |
| Constant disturbance | Constructed from published equation | 1.48267e-11 | 2.41814e-11 |
| Constant clipped torque | Constructed from published equation | 1.51355e-16 | 6.93890e-18 |

For the four linear cases, an independent damped-oscillator energy bound ensures that the command remains inside the declared actuator capacity for all time. Thus the linear closed form is applicable, rather than assuming unsaturation from discrete samples alone. The fifth case uses the separate all-time command lower bound stated above.

## Remaining gaps

Clipping/release transitions, near-critical ill-conditioned roots, extreme input scales, and externally validated real spacecraft data are not benchmarked here. Existing internal tests are not relabeled external evidence. There is no external nonlinear solver comparison: SciPy was unavailable, and no dependency was installed for this bounded milestone. Real sensors, delays, digital control, three-axis motion, flexible modes and reaction-wheel momentum remain outside the maintained model. The sources neither endorse 6D nor validate user-supplied inertia, gains or disturbances.

Reproduce from the repository root: `python tools/published_control_benchmarks.py`. It prints finite JSON and returns a failing exit status if any case fails. The integrated benchmark runner records these same receipts.
