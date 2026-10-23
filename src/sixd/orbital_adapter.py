"""Project-bound orbital evidence, with a stable version-one receipt contract.

Propagation is delegated to the maintained simulation kernel. History validation
checks retained structure, bindings and sample-derived metrics without calling
the solver or applying today's numerical-domain policy to an old receipt.
"""
from __future__ import annotations

import math
import re
import json

from . import simulation


PARAMETERS = {
    "mu_m3_s2": "m^3/s^2", "exclusion_radius_m": "m",
    "position_x": "m", "position_y": "m", "position_z": "m",
    "velocity_x": "m/s", "velocity_y": "m/s", "velocity_z": "m/s",
    "duration_s": "s", "steps": "1",
}
METRIC_UNITS = {
    "min_radius_m": "m", "max_radius_m": "m", "max_speed_m_s": "m/s",
    "final_radius_m": "m", "final_speed_m_s": "m/s",
}
ASSUMPTIONS = [
    "Unforced Newtonian point-mass two-body translation in a three-dimensional, nonrotating body-centered inertial frame; all inputs are explicitly bound SI scalars.",
    "Time starts at the supplied initial state; duration_s is the evaluated window, with steps + 1 stored samples including both endpoints.",
    "Minimum/maximum radius and maximum speed are extrema of stored integration samples over the declared window only; they do not establish continuous-time extrema or safety between samples.",
    "Final radius and speed refer only to the last stored sample at duration_s, not to arrival, landing or completion of a mission.",
    "Requirement comparisons use numerical predictions at the selected fixed resolution, without an uncertainty allowance or numerical-error margin unless explicitly supplied in a project criterion.",
]
NOT_ASSESSED = [
    "Physical applicability and accuracy of supplied initial conditions, gravitational parameter, exclusion radius and input sources.",
    "Between-sample constraint violations, behavior beyond the declared duration, and numerical position/phase error bounds; conservation diagnostics are not engineering pass/fail metrics.",
    "Launch, landing, thrust, mass change, attitude, GNC, atmosphere, drag, heating, structures, body shape, terrain, oblateness, third-body forces and relativity.",
    "Hardware or flight validation, uncertainty, collision certification, complete mission success and launch authorization.",
    "Coupling to other project models is not inferred; thermal, propulsion or structural changes affect this trajectory only through explicitly bound inputs.",
]


def scenario_from_parameters(parameters):
    """Convert the fixed v1 scalar binding contract, without numerical defaults."""
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
        raise ValueError("Orbital trajectory requires every declared scalar parameter exactly once.")
    values = {}
    for key, value in parameters.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Orbital parameter {key} must be a finite number.")
        try:
            values[key] = float(value)
        except (ValueError, OverflowError):
            raise ValueError(f"Orbital parameter {key} must be a finite number.") from None
        if not math.isfinite(values[key]):
            raise ValueError(f"Orbital parameter {key} must be a finite number.")
    if not values["steps"].is_integer():
        raise ValueError("Orbital steps must be an integer-valued number.")
    return {
        "schema": "sixd.orbit-scenario.v1", "name": "Project-bound orbital trajectory",
        "mu_m3_s2": values["mu_m3_s2"], "exclusion_radius_m": values["exclusion_radius_m"],
        "position_m": [values[f"position_{axis}"] for axis in "xyz"],
        "velocity_m_s": [values[f"velocity_{axis}"] for axis in "xyz"],
        "duration_s": values["duration_s"], "steps": int(values["steps"]),
        "frame": "body_centered_inertial_3d",
        "source": "Explicit scalar inputs bound by orbital_trajectory; individual input IDs, units and source labels are retained in the project review.",
    }


def sampled_metrics(artifact):
    """The five assessable v1 metrics, derived from the actual stored samples."""
    samples = artifact["samples"]
    return {
        "min_radius_m": {"value": min(row["radius_m"] for row in samples), "unit": "m"},
        "max_radius_m": {"value": max(row["radius_m"] for row in samples), "unit": "m"},
        "max_speed_m_s": {"value": max(row["speed_m_s"] for row in samples), "unit": "m/s"},
        "final_radius_m": {"value": samples[-1]["radius_m"], "unit": "m"},
        "final_speed_m_s": {"value": samples[-1]["speed_m_s"], "unit": "m/s"},
    }


def evaluate(parameters, *, method="rk4"):
    artifact = simulation.simulate(scenario_from_parameters(parameters), method=method)
    return sampled_metrics(artifact), artifact


ACCURACY_SCHEMA = "sixd.orbit-accuracy.v1"
ACCURACY_METHOD = {
    "name": "three_grid_aligned_state_refinement", "expected_order": 2,
    "accepted_order_min": 1.8, "accepted_order_max": 2.2,
    "error_bound_claimed": False,
}
ACCURACY_LIMITATIONS = [
    "Refinement compares numerical solutions of the same supplied two-body model; it does not establish physical applicability or validate initial conditions.",
    "The maximum differences cover aligned stored samples only, without interpolation or a continuous-time error guarantee.",
    "Second-order refinement and a small fine/middle difference are numerical evidence, not a rigorous bound on the unknown true trajectory error.",
    "Energy and angular-momentum conservation cannot establish position, phase or velocity accuracy and are not used by this assessment.",
    "The current steps value is the finest grid. No automatic resolution increase, new tolerance or mission-success claim is inferred.",
]


def validate_accuracy_criteria(criteria):
    """Return explicit SI criteria, never inventing an accuracy requirement."""
    if criteria is None:
        return None
    fields = {"position_tolerance_m", "velocity_tolerance_m_s", "source"}
    if not isinstance(criteria, dict) or set(criteria) != fields:
        raise ValueError("Orbital accuracy requires exactly position_tolerance_m, velocity_tolerance_m_s and source.")
    result = {}
    for key in ("position_tolerance_m", "velocity_tolerance_m_s"):
        value = criteria[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Orbital accuracy {key} must be a positive finite SI number.")
        try:
            value = float(value)
        except (ValueError, OverflowError):
            raise ValueError(f"Orbital accuracy {key} must be a positive finite SI number.") from None
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Orbital accuracy {key} must be a positive finite SI number.")
        result[key] = value
    if not isinstance(criteria["source"], str) or not criteria["source"].strip():
        raise ValueError("Orbital accuracy source must identify the supplied accuracy requirement.")
    result["source"] = criteria["source"].strip()
    return result


def _compare_aligned(coarse, fine):
    coarse_steps = coarse["spec"]["steps"]
    fine_steps = fine["spec"]["steps"]
    if fine_steps != 2 * coarse_steps:
        raise ValueError("Orbital accuracy reference grids must refine by a factor of two.")
    position = velocity = 0.0
    for index, left in enumerate(coarse["samples"]):
        right = fine["samples"][2 * index]
        # Both states represent duration * index / coarse_steps. Floating-point
        # timestamps need not round identically after doubling numerator/grid.
        position = max(position, math.hypot(*(a - b for a, b in zip(left["position_m"], right["position_m"]))))
        velocity = max(velocity, math.hypot(*(a - b for a, b in zip(left["velocity_m_s"], right["velocity_m_s"]))))
    return {
        "coarse_steps": coarse_steps, "fine_steps": fine_steps,
        "aligned_sample_count": len(coarse["samples"]),
        "max_position_difference_m": position,
        "max_velocity_difference_m_s": velocity,
    }


def _refinement_order(coarse_difference, fine_difference):
    if coarse_difference <= 0.0 or fine_difference <= 0.0:
        return None
    return math.log2(coarse_difference) - math.log2(fine_difference)


def _accuracy_receipt(finest, criteria, levels, failure):
    """Build the entire verdict from retained evidence, without propagation."""
    modern = finest["method"]["name"] == "rk4"
    policy = dict(ACCURACY_METHOD)
    limitations = list(ACCURACY_LIMITATIONS)
    if modern:
        policy.update(expected_order=4, accepted_order_min=3.7, accepted_order_max=4.5)
        limitations[2] = "Fourth-order refinement and a small fine/middle difference are numerical evidence, not a rigorous bound on the unknown true trajectory error."
    receipt = {
        "schema": "sixd.orbit-accuracy.v2" if modern else ACCURACY_SCHEMA, "status": "not_assessed", "criteria": criteria,
        "reason": "", "method": policy,
        "reference_levels": levels, "reference_failure": failure,
        "comparisons": [], "observed_orders": {"position": None, "velocity": None},
        "limitations": limitations,
    }
    steps = finest["spec"]["steps"]
    if criteria is None:
        receipt["reason"] = "No position and velocity accuracy criteria were supplied; numerical accuracy is not assessed."
        return receipt
    if steps < 64 or steps % 4:
        receipt["reason"] = "Three-grid refinement requires a finest steps value divisible by four and at least 64; the finest trajectory is retained without an accuracy assessment."
        return receipt
    if failure is not None:
        receipt["reason"] = f"Reference grid with {failure['steps']} steps could not be calculated: {failure['message']} Finest trajectory retained; numerical accuracy is not assessed."
        return receipt
    if len(levels) != 2:
        raise ValueError("Orbital accuracy requires both coarser reference levels.")
    coarse, middle = [level["artifact"] for level in levels]
    comparisons = [_compare_aligned(coarse, middle), _compare_aligned(middle, finest)]
    receipt["comparisons"] = comparisons
    orders = {
        "position": _refinement_order(*(row["max_position_difference_m"] for row in comparisons)),
        "velocity": _refinement_order(*(row["max_velocity_difference_m_s"] for row in comparisons)),
    }
    receipt["observed_orders"] = orders
    if any(value is None for value in orders.values()):
        receipt["reason"] = "The retained grid differences do not establish a measurable refinement order; numerical accuracy is not assessed."
    elif not all(policy["accepted_order_min"] <= value <= policy["accepted_order_max"] for value in orders.values()):
        receipt["status"] = "insufficient_accuracy"
        receipt["reason"] = ("The retained position and velocity differences do not both show the required fourth-order refinement (observed order 3.7 through 4.5)." if modern else "The retained position and velocity differences do not both show the required second-order refinement (observed order 1.8 through 2.2).")
    elif (comparisons[-1]["max_position_difference_m"] > criteria["position_tolerance_m"]
          or comparisons[-1]["max_velocity_difference_m_s"] > criteria["velocity_tolerance_m_s"]):
        receipt["status"] = "insufficient_accuracy"
        receipt["reason"] = "The worst aligned fine/middle position or velocity difference exceeds a supplied accuracy tolerance."
    else:
        receipt["status"] = "supported"
        receipt["reason"] = ("Aligned fine/middle position and velocity differences meet the supplied tolerances, with observed fourth-order refinement; this is not a rigorous true-error bound." if modern else "Aligned fine/middle position and velocity differences meet the supplied tolerances, with observed second-order refinement; this is not a rigorous true-error bound.")
    return receipt


def evaluate_with_accuracy(parameters, criteria=None, *, method="rk4"):
    """Keep the declared finest result and assess explicit accuracy criteria.

    At most two extra bounded propagations run. Their retained states make the
    refinement arithmetic independently inspectable without rerunning a solver.
    Failure of a coarser grid never discards an already valid finest trajectory.
    """
    criteria = validate_accuracy_criteria(criteria)
    metrics, finest = evaluate(parameters, method=method)
    levels, failure = [], None
    steps = finest["spec"]["steps"]
    if criteria is not None and steps >= 64 and steps % 4 == 0:
        for reference_steps in (steps // 4, steps // 2):
            reference_parameters = dict(parameters, steps=reference_steps)
            try:
                _, artifact = evaluate(reference_parameters, method=method)
            except ValueError as error:
                failure = {"steps": reference_steps, "message": str(error)}
                break
            levels.append({"steps": reference_steps, "artifact": artifact})
    return metrics, finest, _accuracy_receipt(finest, criteria, levels, failure)


def _fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"Orbital {label} has an inconsistent v1 structure.")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Orbital {label} must be a finite number.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"Orbital {label} must be a finite number.")


def validate_artifact(artifact, metrics, parameters, retained_source):
    """Check immutable v1 evidence without rerunning or authenticating physics.

    The full review digest retains the other method/diagnostic/limitation fields.
    Checking vector-derived radii/speeds and summary extrema catches mismatched
    evidence even when a caller recomputes outer unsigned digests.
    """
    _fields(artifact, {"schema", "spec", "source_fingerprint", "method", "units", "samples",
                       "summary", "limits", "diagnostics_label", "limitations"}, "artifact")
    spec = scenario_from_parameters(parameters)
    if artifact["schema"] != "sixd.orbit-simulation.v1" or artifact["spec"] != spec:
        raise ValueError("Orbital artifact does not match the bound project scenario.")
    if (not isinstance(retained_source, str) or re.fullmatch(r"[0-9a-f]{64}", retained_source) is None
            or artifact["source_fingerprint"] != retained_source):
        raise ValueError("Orbital artifact does not match its retained solver source fingerprint.")
    method = artifact["method"]
    _fields(method, {"name", "version", "order", "time_step_s", "steps", "force_model",
                     "coordinates", "sampling"}, "method")
    if ((method["name"], method["version"], method["order"]) not in {("velocity_verlet", "1", 2), ("rk4", "2", 4)}
            or isinstance(method["order"], bool) or isinstance(method["steps"], bool)
            or not isinstance(method["steps"], int) or method["steps"] != spec["steps"]
            or method["force_model"] != "newtonian_point_mass_two_body"
            or not isinstance(method["coordinates"], str) or not method["coordinates"]
            or not isinstance(method["sampling"], str) or not method["sampling"]):
        raise ValueError("Orbital method does not match the v1 integration contract.")
    _number(method["time_step_s"], "time step")
    # Permanent v1 serialization bounds, independent of later solver policy.
    if not 16 <= spec["steps"] <= (16384 if method["name"] == "rk4" else 4096) or spec["duration_s"] <= 0 or spec["mu_m3_s2"] <= 0:
        raise ValueError("Orbital retained v1 scenario bounds are inconsistent.")
    if method["time_step_s"] != spec["duration_s"] / spec["steps"]:
        raise ValueError("Orbital time step does not match the bound window.")
    units = {"time": "s", "position": "m", "velocity": "m/s",
             "specific_energy": "J/kg", "specific_angular_momentum": "m^2/s"}
    if artifact["units"] != units:
        raise ValueError("Orbital artifact units do not match the fixed SI contract.")
    samples = artifact["samples"]
    if not isinstance(samples, list) or len(samples) != spec["steps"] + 1:
        raise ValueError("Orbital sample count does not match its integration steps.")
    for index, row in enumerate(samples):
        _fields(row, {"time_s", "position_m", "velocity_m_s", "radius_m", "speed_m_s",
                      "specific_energy_j_kg"}, "sample")
        for key in ("time_s", "radius_m", "speed_m_s", "specific_energy_j_kg"):
            _number(row[key], "sample " + key)
        for key in ("position_m", "velocity_m_s"):
            if not isinstance(row[key], list) or len(row[key]) != 3:
                raise ValueError("Orbital sample vectors must contain three components.")
            for component in row[key]:
                _number(component, "sample component")
        expected_time = spec["duration_s"] if method["name"] == "rk4" and index == spec["steps"] else spec["duration_s"] * index / spec["steps"]
        if row["time_s"] != expected_time:
            raise ValueError("Orbital sample times do not match the stored window and grid.")
        if (row["radius_m"] != math.hypot(*row["position_m"])
                or row["speed_m_s"] != math.hypot(*row["velocity_m_s"])):
            raise ValueError("Orbital scalar samples disagree with their position/velocity vectors.")
    if samples[0]["position_m"] != spec["position_m"] or samples[0]["velocity_m_s"] != spec["velocity_m_s"]:
        raise ValueError("Orbital first sample does not match the bound initial state.")
    expected_metrics = sampled_metrics(artifact)
    if metrics != expected_metrics:
        raise ValueError("Orbital engineering metrics disagree with the stored trajectory samples.")
    summary = artifact["summary"]
    _fields(summary, {"sample_count", "min_radius_m", "max_radius_m", "max_speed_m_s",
                      "initial_specific_energy_j_kg", "final_specific_energy_j_kg", "max_relative_energy_error",
                      "max_relative_angular_momentum_error", "semi_major_axis_m", "eccentricity",
                      "pericenter_radius_m", "apocenter_radius_m", "orbital_period_s"}, "summary")
    for key, value in summary.items():
        _number(value, "summary " + key)
    if summary["sample_count"] != len(samples) or not isinstance(summary["sample_count"], int):
        raise ValueError("Orbital summary sample count is inconsistent.")
    for key in ("min_radius_m", "max_radius_m", "max_speed_m_s"):
        if summary[key] != expected_metrics[key]["value"]:
            raise ValueError("Orbital summary extrema disagree with the retained samples.")
    if (summary["initial_specific_energy_j_kg"] != samples[0]["specific_energy_j_kg"]
            or summary["final_specific_energy_j_kg"] != samples[-1]["specific_energy_j_kg"]):
        raise ValueError("Orbital summary endpoint energy is inconsistent.")
    _fields(artifact["limits"], {"max_steps", "max_eccentricity", "max_orbital_periods",
                               "max_pericenter_step_ratio", "actual_pericenter_step_ratio",
                               "pericenter_clearance_factor"}, "limits")
    for key, value in artifact["limits"].items():
        _number(value, "limit " + key)
    if (not isinstance(artifact["diagnostics_label"], str) or not artifact["diagnostics_label"]
            or not isinstance(artifact["limitations"], list)
            or not artifact["limitations"] or any(not isinstance(item, str) or not item for item in artifact["limitations"])):
        raise ValueError("Orbital diagnostics and limitations must remain explicit.")
    return True


def validate_accuracy(accuracy, finest_artifact, parameters, criteria, source_fingerprint):
    """Validate saved refinement arithmetic without invoking today's solver.

    This is unsigned receipt consistency, not authentication of an external
    physical experiment. Historical v1 artifacts keep their existing validator.
    """
    criteria = validate_accuracy_criteria(criteria)
    validate_artifact(finest_artifact, sampled_metrics(finest_artifact), parameters, source_fingerprint)
    fields = {"schema", "status", "criteria", "reason", "method", "reference_levels",
              "reference_failure", "comparisons", "observed_orders", "limitations"}
    _fields(accuracy, fields, "accuracy receipt")
    levels = accuracy["reference_levels"]
    if not isinstance(levels, list) or len(levels) > 2:
        raise ValueError("Orbital accuracy must retain at most two coarser reference grids.")
    steps = finest_artifact["spec"]["steps"]
    eligible = criteria is not None and steps >= 64 and steps % 4 == 0
    if not eligible and (levels or accuracy["reference_failure"] is not None):
        raise ValueError("Orbital accuracy reference grids are inconsistent with the declared criteria or step grid.")
    for index, level in enumerate(levels):
        _fields(level, {"steps", "artifact"}, "accuracy reference level")
        expected_steps = steps // (4 if index == 0 else 2)
        if isinstance(level["steps"], bool) or not isinstance(level["steps"], int) or level["steps"] != expected_steps:
            raise ValueError("Orbital accuracy reference steps do not match the retained refinement levels.")
        reference_parameters = dict(parameters, steps=expected_steps)
        artifact = level["artifact"]
        validate_artifact(artifact, sampled_metrics(artifact), reference_parameters, source_fingerprint)
        if any(artifact["method"][key] != finest_artifact["method"][key] for key in ("name", "version", "order")):
            raise ValueError("Refinement grids must use the same retained numerical method.")
    failure = accuracy["reference_failure"]
    if failure is not None:
        _fields(failure, {"steps", "message"}, "accuracy reference failure")
        if len(levels) >= 2:
            raise ValueError("Orbital accuracy cannot declare a failed reference after both reference grids completed.")
        expected_steps = steps // (4 if len(levels) == 0 else 2)
        if (isinstance(failure["steps"], bool) or not isinstance(failure["steps"], int)
                or failure["steps"] != expected_steps
                or not isinstance(failure["message"], str) or not failure["message"].strip()):
            raise ValueError("Orbital accuracy reference failure is inconsistent with the retained grid sequence.")
    expected = _accuracy_receipt(finest_artifact, criteria, levels, failure)
    try:
        actual_json = json.dumps(accuracy, sort_keys=True, separators=(",", ":"), allow_nan=False)
        expected_json = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Orbital accuracy receipt must contain finite JSON-compatible evidence.") from None
    if actual_json != expected_json:
        raise ValueError("Orbital accuracy receipt disagrees with its criteria, retained grids or recomputed refinement arithmetic.")
    return True
