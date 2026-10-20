# Single-axis spacecraft pointing

The maintained `attitude_control` adapter adds an ideal single-axis pointing response to 6D's existing requirements, revisions, scenarios, scalar test comparison, Assistant and reporting workflow. It is the first quantitative control capability, not complete GNC coverage. Existing unsupported navigation, tracking and whole-vehicle control requirements remain unassessed unless explicitly remapped to a genuinely applicable supported metric.

## Use in the workspace

Open **Guidance & control → Open constructed reference → Create project → Run saved checks**. The example is a separate constructed project. Its values are analytical test inputs, not a real spacecraft. The response shows signed error, angular rate, requested torque and applied actuator torque. Inspect a requirement for its separate criterion and evidence; Investigate opens the scoped Assistant without starting inference.

To supply a different project, use **Author project** to add explicit sourced SI inputs, choose **Single-axis spacecraft pointing**, bind every parameter, and declare requirements. Save the shared draft before running. **Inspect or edit inputs** opens the same Table/Inspector workflow. A control input change reruns control, while unchanged independent models can reuse evidence. A limit-only revision reassesses criteria against the unchanged response. Drafts have no new calculated plots.

The full report includes sampled metrics, histories, grid diagnostics, witness rows, assumptions, exclusions and receipt/source identities. JSON retains all saved samples. Browser plots display server-recorded evidence only; navigation does not integrate dynamics or call a model provider.

## Model and units

The unchanged project schema is `sixd.project.v1`. A model has `id`, `type: attitude_control`, `inputs` mapping every role below to a sourced project input, and optional `description`. No defaults or unit conversion are inferred.

| Parameter | Exact unit | Meaning |
| --- | --- | --- |
| inertia | kg*m^2 | Positive constant inertia about the chosen principal axis |
| initial_angle | rad | Initial signed, unwrapped angle in the declared axis/reference |
| initial_rate | rad/s | Initial signed angular rate |
| target_angle | rad | Constant target angle in that same reference |
| proportional_gain | N*m/rad | Nonnegative proportional gain |
| derivative_gain | N*m*s/rad | Nonnegative rate-feedback gain |
| max_torque | N*m | Nonnegative symmetric actuator torque limit |
| disturbance_torque | N*m | Signed constant externally supplied disturbance torque |
| duration | s | Positive simulation duration |
| steps | 1 | Integer coarse-grid interval count from 32 to 2048; saved grid has twice as many intervals |
| assessment_start | s | Start of sampled assessment window, from zero through duration inclusive |
| angle_numerical_tolerance | rad | Positive permitted coarse/fine common-time error disagreement |
| rate_numerical_tolerance | rad/s | Positive permitted coarse/fine common-time rate disagreement |

All values must be finite numbers. Zero gain or torque capacity is permitted to represent a deliberately inactive controller or actuator. This may violate engineering criteria while remaining a valid completed calculation. The axis and reference must be supplied consistently in the project's descriptions/sources; their physical compatibility is not inferred or verified. SI exponent typography remains a later display refinement; stored units remain explicit ASCII contracts.

## Equations

For inertia I, angle theta, rate omega, constant target theta_target, gains kp and kd, actuator limit U, and constant disturbance d:

```text
error = theta_target - theta
requested_torque = kp * error - kd * omega
applied_torque = clip(requested_torque, -U, U)
d(error)/dt = -omega
d(omega)/dt = (applied_torque + d) / I
theta = theta_target - error
```

The disturbance is added after actuator clipping. The desired rate is zero. Angles are not wrapped and the controller does not select a shortest rotation. This is continuous ideal feedback using perfect state knowledge; integration steps are not a flight controller's sample period. The actuator is an ideal torque source with unlimited operation within its torque bound. No wheel speed/momentum, desaturation, actuator dynamics, power consumption or propellant use is modeled.

## Numerical contract

Classical fixed-step RK4 runs on N and 2N intervals, restarting both from the same supplied initial state. Maximum absolute error and rate disagreement are compared at every common time. If either exceeds its supplied numerical tolerance, execution abstains with `invalid_inputs`, empty metrics and no completed response. Numerical tolerances are distinct from engineering requirement limits. Passing grid agreement does not certify absolute accuracy, stability or model validity; especially near a criterion, refine resolution and obtain independent evidence.

The coarse step h must satisfy `h * max(sqrt(kp/I), kd/I) <= 0.1`. This resolution guard avoids accepting a trivially coarse sample of fast controller dynamics; it is not a general control-stability proof. Initial angles, rate, initial error, and computed angle/error/rate magnitudes are bounded by 1000000 in their respective units as computational limits. Nonfinite arithmetic, nonzero products/ratios that underflow to zero, or indistinguishable time samples cause abstention. Floating-point roundoff still exists. There is no automatic retry, gain tuning, limit relaxation or adaptive extension of the run.

The `attitude_response` artifact has schema `sixd.attitude-response.v1`, normalized parameters, solver metadata, 2N+1 fine-grid samples, diagnostics, source fingerprint, assumptions and exclusions. Each sample stores time, unwrapped angle, signed error/rate, requested/applied torque and a boolean indicating strict command clipping. At exact command/limit equality, the command is not clipped.

History verification checks its retained schema, source identity, sample times, input/initial-state binding, algebraic angle and torque relationships, metrics and diagnostic bounds. It does not reintegrate, authenticate an author, validate hardware or establish truth against deliberately forged coherent data. Project imports do not accept externally asserted result artifacts. A deliberately requested same-adapter recheck performs a fresh integration and tests reproducibility. Historical three-file and five-file source manifests remain readable; new attitude results require the complete six-file manifest including `attitude.py`.

## Supported criteria

| Metric | Unit | Definition |
| --- | --- | --- |
| final_error | rad | Absolute error at the final saved sample |
| final_rate | rad/s | Absolute rate at the final saved sample |
| max_sampled_error | rad | Maximum absolute error over all saved samples |
| max_sampled_rate | rad/s | Maximum absolute rate over all saved samples |
| max_assessed_error | rad | Maximum absolute error at saved times at or after assessment_start |
| max_assessed_rate | rad/s | Maximum absolute rate at saved times at or after assessment_start |
| max_sampled_command_torque | N*m | Maximum requested-torque magnitude over saved samples |
| max_sampled_applied_torque | N*m | Maximum applied-actuator-torque magnitude over saved samples |
| sampled_saturation_fraction | 1 | Count of clipped-command samples divided by total saved sample count |

The first included assessment time and sample count are disclosed. If the requested start lies between samples, it is not interpolated. Starting at the endpoint assesses only that endpoint. A fraction of clipped samples is not a duration fraction. A final value does not establish settling time. Extrema do not establish continuous-time bounds, and no whole-project green light is inferred.

## Independent witnesses and constructed reference

The example uses I=10, kp=1, kd=2*sqrt(10), initial angle/rate zero, target 0.2 rad, no disturbance, and sufficient torque authority to stay unsaturated. With n=sqrt(kp/I), the independent critical-damping solution is:

```text
error(t) = 0.2 * (1+n*t) * exp(-n*t)
omega(t) = 0.2 * n*n*t * exp(-n*t)
```

Tests compare every saved sample with these formulas. Further independent witnesses cover free rotation, constant external torque, a continuously clipped torque with quadratic angle, undamped cosine motion with fourth-order refinement, and an overdamped pair of exponentials. Disturbance exceeding opposing actuator torque, released/reversed clipping, sign symmetry, invalid units/parameters, corrupted evidence and numerical-bound failures are checked separately. These establish behavior within the declared mathematical model; they do not validate a spacecraft.

## Scope and sources

NASA distinguishes GNC's sensing/estimation and actuation functions and describes spacecraft pointing technologies: [NASA, Guidance, Navigation, and Control](https://www.nasa.gov/smallsat-institute/sst-soa/guidance-navigation-and-control/). The control-loop context of desired orientation, error, control torque, spacecraft and disturbance is illustrated in [Space Vehicle Control Systems, NASA-hosted engineering reference](https://s3vi.ndc.nasa.gov/ssri-kb/static/resources/III.4.3.1_Space_Vehicle_Control_Systems.pdf). Reviewed October 18, 2026. These sources provide context; they do not endorse this adapter or supplied data. The equations and analytic test witnesses above state the exact simplification implemented.

Excluded: three-axis attitude dynamics, flexible structure effects, sensors/noise/estimation, navigation, moving-target guidance, digital implementation and delays, reaction-wheel momentum, real actuator constraints, orbital/thermal/electrical coupling, environmental torque prediction, continuous-time guarantees, uncertainty, qualification, rocket landing and launch authorization. New Assistant evidence context is tested offline; no new live Nebius quality claim is made in this milestone.
