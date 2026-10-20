"""External-equation checks for the bounded single-axis attitude calculator.

Reference functions below contain closed forms only. They never call 6D's
derivative, integrator, sampled_metrics, or other calculation helpers.
The two MIT worked solutions retain their published states and coefficients;
the other cases are explicitly constructed applications of published roots.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


WORKED_SOURCE = (
    "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/"
    "79f2349d10404454ea6ed6f959fc1d33_MIT18_03SCF11_rec_08s13_sol.pdf"
)
ROOTS_SOURCE = (
    "https://ocw.mit.edu/courses/res-8-009-introduction-to-oscillations-and-waves-"
    "summer-2017/mitres_8_009su17_lec4.pdf"
)
ROTATION_SOURCE = (
    "https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/"
    "f50ece7a5a7980dc9d24fe8376a9978c_X9K8LT7SCZ0.pdf"
)


def _published_underdamped(time: float) -> tuple[float, float]:
    """MIT 18.03SC Practice Problems 10 Q2: x=exp(-t/2)*cos(3t)."""
    envelope = math.exp(-time / 2)
    return (envelope * math.cos(3 * time),
            envelope * (-.5 * math.cos(3 * time) - 3 * math.sin(3 * time)))


def _published_critical(time: float) -> tuple[float, float]:
    """MIT 18.03SC Practice Problems 10 Q5: x=(2+5t)*exp(-t)."""
    return ((2 + 5 * time) * math.exp(-time),
            (3 - 5 * time) * math.exp(-time))


def _constructed_solution(parameters: dict, time: float) -> tuple[float, float]:
    """Closed-form characteristic-root solution, no time integration.

    With theta as displacement and a constant disturbance d,
    theta_eq = target + d/kp. Thus x=theta-theta_eq satisfies
    I*x''+kd*x'+kp*x=0. Initial constants are solved algebraically.
    These constructed cases have kp>0 and stay strictly unsaturated.
    """
    inertia = parameters["inertia"]
    stiffness = parameters["proportional_gain"]
    damping = parameters["derivative_gain"]
    equilibrium = parameters["target_angle"] + parameters["disturbance_torque"] / stiffness
    x0 = parameters["initial_angle"] - equilibrium
    v0 = parameters["initial_rate"]
    gamma = damping / (2 * inertia)
    discriminant = gamma * gamma - stiffness / inertia
    if discriminant < 0:
        frequency = math.sqrt(-discriminant)
        a = x0
        b = (v0 + gamma * x0) / frequency
        co, si = math.cos(frequency * time), math.sin(frequency * time)
        transient = math.exp(-gamma * time) * (a * co + b * si)
        rate = math.exp(-gamma * time) * (
            -gamma * (a * co + b * si) + frequency * (-a * si + b * co)
        )
    elif discriminant > 0:
        root = math.sqrt(discriminant)
        r1, r2 = -gamma + root, -gamma - root
        a = (v0 - r2 * x0) / (r1 - r2)
        b = x0 - a
        transient = a * math.exp(r1 * time) + b * math.exp(r2 * time)
        rate = a * r1 * math.exp(r1 * time) + b * r2 * math.exp(r2 * time)
    else:
        a, b = x0, v0 + gamma * x0
        transient = (a + b * time) * math.exp(-gamma * time)
        rate = (b - gamma * (a + b * time)) * math.exp(-gamma * time)
    return equilibrium + transient, rate


def _parameters(**changes) -> dict:
    parameters = {
        "inertia": 1., "initial_angle": 1., "initial_rate": -.5,
        "target_angle": 0., "proportional_gain": 37 / 4,
        "derivative_gain": 1., "max_torque": 100., "disturbance_torque": 0.,
        "duration": 4., "steps": 512, "assessment_start": 1.17,
        "angle_numerical_tolerance": 1e-7, "rate_numerical_tolerance": 1e-7,
    }
    parameters.update(changes)
    return parameters


def _check(case_id, parameters, reference, sources, reference_kind, description,
           always_clipped=False):
    # This import/call is the system under test, never the expected-value path.
    from sixd import attitude

    metrics, artifact = attitude.evaluate(parameters)
    samples = artifact["samples"]
    reference_rows = [reference(parameters["duration"] * i / (2 * parameters["steps"]))
                      for i in range(2 * parameters["steps"] + 1)]
    expected_count = 2 * parameters["steps"] + 1
    max_angle_error = max(abs(row["angle_rad"] - ref[0])
                          for row, ref in zip(samples, reference_rows))
    max_rate_error = max(abs(row["rate_rad_s"] - ref[1])
                         for row, ref in zip(samples, reference_rows))
    max_error_error = max(abs(row["error_rad"] - (parameters["target_angle"] - ref[0]))
                          for row, ref in zip(samples, reference_rows))
    max_command_error = max(abs(row["command_torque_nm"] - (
        parameters["proportional_gain"] * (parameters["target_angle"] - ref[0])
        - parameters["derivative_gain"] * ref[1]))
        for row, ref in zip(samples, reference_rows))
    expected_commands = [parameters["proportional_gain"] * (parameters["target_angle"] - ref[0])
                         - parameters["derivative_gain"] * ref[1] for ref in reference_rows]
    # This independently sufficient all-time bound avoids mistaking a sampled
    # absence of clipping for evidence that the reference is unsaturated.
    # Oscillator energy decreases for kd>=0: |x|<=sqrt(x0²+I*v0²/kp),
    # |rate|<=sqrt(v0²+kp*x0²/I). Constant disturbance is shifted to equilibrium.
    if always_clipped:
        # The declared constructed case has command(t)=2-.01*t²-.01*t.
        # Its derivative is negative throughout [0,1], so its endpoint is a
        # rigorous lower bound. No sampled-clipping inference is used.
        command_bound = 2 - .01 * parameters["duration"]**2 - .01 * parameters["duration"]
        reference_condition_met = command_bound > parameters["max_torque"]
        bound_label = "Analytic command lower bound in the declared 0..1 s case, N*m"
        expected_applied = [parameters["max_torque"] for _ in reference_rows]
    else:
        equilibrium = parameters["target_angle"] + parameters["disturbance_torque"] / parameters["proportional_gain"]
        x0 = parameters["initial_angle"] - equilibrium
        max_displacement = math.sqrt(x0*x0 + parameters["inertia"] * parameters["initial_rate"]**2 / parameters["proportional_gain"])
        max_rate = math.sqrt(parameters["initial_rate"]**2 + parameters["proportional_gain"] * x0*x0 / parameters["inertia"])
        command_bound = (parameters["proportional_gain"] * max_displacement
                         + parameters["derivative_gain"] * max_rate
                         + abs(parameters["disturbance_torque"]))
        reference_condition_met = command_bound < parameters["max_torque"]
        bound_label = "Conservative all-time absolute command upper bound from damped-oscillator energy, N*m"
        expected_applied = expected_commands
    max_applied_error = max(abs(row["applied_torque_nm"] - expected)
                            for row, expected in zip(samples, expected_applied))
    selected = sorted({0, len(samples)//4, len(samples)//2, 3*len(samples)//4, len(samples)-1})
    expected = {
        "sample_count": expected_count,
        "final_angle_rad": reference_rows[-1][0],
        "final_rate_rad_s": reference_rows[-1][1],
        "maximum_angle_difference_rad": 0.,
        "maximum_rate_difference_rad_s": 0.,
        "maximum_signed_error_difference_rad": 0.,
        "maximum_command_difference_nm": 0.,
        "maximum_applied_torque_difference_nm": 0.,
        "sampled_saturation_fraction": float(always_clipped),
        "selected_samples": [{"time_s": parameters["duration"] * i / (2 * parameters["steps"]),
                              "angle_rad": reference_rows[i][0], "rate_rad_s": reference_rows[i][1]}
                             for i in selected],
    }
    actual = {
        "sample_count": len(samples),
        "final_angle_rad": samples[-1]["angle_rad"],
        "final_rate_rad_s": samples[-1]["rate_rad_s"],
        "maximum_angle_difference_rad": max_angle_error,
        "maximum_rate_difference_rad_s": max_rate_error,
        "maximum_signed_error_difference_rad": max_error_error,
        "maximum_command_difference_nm": max_command_error,
        "maximum_applied_torque_difference_nm": max_applied_error,
        "sampled_saturation_fraction": metrics["sampled_saturation_fraction"]["value"],
        "selected_samples": [{key: samples[i][key] for key in ("time_s", "angle_rad", "rate_rad_s")}
                             for i in selected],
    }
    tolerance = {"angle_absolute_rad": 1e-8, "rate_absolute_rad_s": 1e-8,
                 "command_absolute_nm": 1e-7, "sample_count_exact": True,
                 "saturation_fraction_exact": True}
    passed = (len(samples) == expected_count and max_angle_error <= 1e-8
              and max_error_error <= 1e-8 and max_rate_error <= 1e-8
              and max_command_error <= 1e-7 and max_applied_error <= 1e-7
              and reference_condition_met
              and actual["sampled_saturation_fraction"] == float(always_clipped))
    return {
        "id": case_id, "model": "attitude_control", "source_urls": sources,
        "reference_kind": reference_kind, "description": description,
        "inputs": dict(parameters), "expected": expected, "actual": actual,
        "tolerance": tolerance, "passed": passed,
        "reference_method": "Closed-form characteristic roots; every saved sample compared, no numerical reference integrator.",
        "reference_command_bound": {"value": command_bound, "meaning": bound_label,
                                    "reference_condition_met": reference_condition_met},
        "limitations": [
            "Checks mathematical single-axis continuous PD dynamics only, not controller suitability or real spacecraft validity.",
            ("This constructed case remains continuously clipped by a command lower bound; clipping/release transitions are not independently benchmarked."
             if always_clipped else "This case is provably unsaturated by a conservative energy bound; clipping/release transitions are not independently benchmarked."),
            "Angular rates and angles refer to one fixed rigid axis with perfect state feedback; no three-axis dynamics, sensors, delays, wheel momentum or flight qualification.",
            "Published oscillator displacement is mapped to angle relative to a fixed target; the sources do not provide a spacecraft test or endorse this adapter.",
        ],
    }


def run_checks() -> list[dict]:
    """Return five auditable, offline external-equation benchmark receipts."""
    under = _parameters()
    critical = _parameters(initial_angle=2., initial_rate=3., proportional_gain=1.,
                           derivative_gain=2., duration=6., assessment_start=2.03)
    over = _parameters(inertia=2., initial_angle=1., initial_rate=-.2, target_angle=.7,
                       proportional_gain=4., derivative_gain=6., duration=5., assessment_start=1.11)
    disturbed = _parameters(inertia=2., initial_angle=-.2, initial_rate=.1, target_angle=.4,
                            proportional_gain=8., derivative_gain=4., disturbance_torque=.2,
                            duration=8., steps=1024, assessment_start=3.19)
    clipped = _parameters(inertia=10., initial_angle=0., initial_rate=0., target_angle=1.,
                          proportional_gain=2., derivative_gain=1., max_torque=.1,
                          duration=1., steps=64, assessment_start=0.)
    return [
        _check("control_mit_worked_underdamped", under, _published_underdamped,
               [WORKED_SOURCE, ROOTS_SOURCE], "published_worked_solution",
               "MIT Practice Problems 10 Q2: x=e^(-t/2)cos(3t); m=1,b=1,k=37/4 mapped to I,kd,kp. Initial x=1 and derivative=-1/2 follow the published solution."),
        _check("control_mit_worked_critical", critical, _published_critical,
               [WORKED_SOURCE, ROOTS_SOURCE], "published_worked_solution",
               "MIT Practice Problems 10 Q5: x=(2+5t)e^(-t), x(0)=2, x'(0)=3; I=1,kd=2,kp=1."),
        _check("control_constructed_overdamped", over,
               lambda time: _constructed_solution(over, time), [ROOTS_SOURCE],
               "constructed_from_published_equation",
               "Constructed overdamped fixed-target case from characteristic roots; not a published numerical spacecraft example."),
        _check("control_constructed_constant_disturbance", disturbed,
               lambda time: _constructed_solution(disturbed, time), [ROOTS_SOURCE],
               "constructed_from_published_equation",
               "Constructed constant-disturbance case. Shift theta by target+d/kp, then use the published homogeneous solution; verifies error and disturbance signs."),
        _check("control_constructed_constant_clipped_torque", clipped,
               lambda time: (.005 * time * time, .01 * time), [ROTATION_SOURCE],
               "constructed_from_published_equation",
               "Constructed constant-clipped-torque case from I*angular_acceleration=torque; command(t)=2-.01t²-.01t >=1.98 N*m over 0..1 s exceeds the .1 N*m limit, so theta=.005t² and rate=.01t.",
               always_clipped=True),
    ]


if __name__ == "__main__":
    import json
    receipts = run_checks()
    print(json.dumps(receipts, indent=2, allow_nan=False))
    raise SystemExit(0 if all(row["passed"] for row in receipts) else 1)
