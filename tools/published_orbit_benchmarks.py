"""Development-only external orbit comparisons; never called by the product.

NASA NAIF CSPICE prop2b/conics, through pinned SpiceyPy, supplies reference
states. No production acceleration, integrator, element extraction or stored
diagnostics are used to compute reference trajectories. See the companion doc.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sixd import orbital_adapter

SPICE_VERSION = "8.3.0"
PROP2B_URL = "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/prop2b_c.html"
CONICS_URL = "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/conics_c.html"
WRAPPER_URL = "https://spiceypy.readthedocs.io/en/v8.3.0/"
MU = 3.986004418e14  # Constructed Earth-like parameter, not an ephemeris claim.

# Declared before running the benchmark. These are benchmark acceptance levels,
# not mission tolerances or error bounds over all supported orbital conditions.
STATE_RELATIVE_TOLERANCE = 0.02
METRIC_RELATIVE_TOLERANCE = 0.01
ORDER_INTERVAL = (1.8, 2.2)
CIRCULAR_FINE_RELATIVE_TOLERANCE = 1e-5


def _spice():
    dependency_dir = ROOT / ".local" / "benchmark-deps"
    if dependency_dir.is_dir():
        sys.path.insert(0, str(dependency_dir))
    try:
        import spiceypy
    except ImportError as exc:
        raise RuntimeError(
            "Independent orbital benchmark requires development-only spiceypy==8.3.0. "
            "Install with python -m pip install --target .local/benchmark-deps "
            "--only-binary=:all: spiceypy==8.3.0. No substitute oracle was run."
        ) from exc
    if spiceypy.__version__ != SPICE_VERSION:
        raise RuntimeError(f"Expected SpiceyPy {SPICE_VERSION}; found {spiceypy.__version__}.")
    return spiceypy


def _norm_error(actual, expected):
    return math.dist(actual, expected)


def _parameters(state, duration, steps):
    return {
        "mu_m3_s2": MU,
        "exclusion_radius_m": 1_000_000.0,
        **{f"position_{axis}": float(state[i]) for i, axis in enumerate("xyz")},
        **{f"velocity_{axis}": float(state[i + 3]) for i, axis in enumerate("xyz")},
        "duration_s": duration,
        "steps": steps,
    }


def _expected_metrics(states):
    radii = [math.hypot(*state[:3]) for state in states]
    speeds = [math.hypot(*state[3:]) for state in states]
    return {
        "min_radius_m": min(radii), "max_radius_m": max(radii),
        "max_speed_m_s": max(speeds), "final_radius_m": radii[-1],
        "final_speed_m_s": speeds[-1],
    }


def _compare(parameters, expected_states, position_scale, velocity_scale):
    metrics, artifact = orbital_adapter.evaluate(parameters)
    actual_states = [row["position_m"] + row["velocity_m_s"] for row in artifact["samples"]]
    position_errors = [_norm_error(a[:3], e[:3]) for a, e in zip(actual_states, expected_states)]
    velocity_errors = [_norm_error(a[3:], e[3:]) for a, e in zip(actual_states, expected_states)]
    expected_metrics = _expected_metrics(expected_states)
    actual_metrics = {key: float(record["value"]) for key, record in metrics.items()}
    relative_metric_errors = {key: abs(actual_metrics[key] - value) / abs(value)
                              for key, value in expected_metrics.items()}
    indices = sorted({0, parameters["steps"] // 4, parameters["steps"] // 2,
                      3 * parameters["steps"] // 4, parameters["steps"]})
    return {
        "expected": {
            "metrics": expected_metrics,
            "checkpoints": [{"sample_index": i, "time_s": artifact["samples"][i]["time_s"],
                             "state_m_and_m_s": list(map(float, expected_states[i]))} for i in indices],
        },
        "actual": {
            "metrics": actual_metrics,
            "checkpoints": [{"sample_index": i, "time_s": artifact["samples"][i]["time_s"],
                             "state_m_and_m_s": actual_states[i]} for i in indices],
            "sample_count": len(actual_states),
            "max_position_error_m": max(position_errors),
            "max_velocity_error_m_s": max(velocity_errors),
            "max_position_error_over_semimajor_axis": max(position_errors) / position_scale,
            "max_velocity_error_over_circular_speed": max(velocity_errors) / velocity_scale,
            "relative_metric_errors": relative_metric_errors,
        },
    }


def _reference_case(spice, name, a, e, inclination_deg, node_deg, periapse_deg,
                    mean_anomaly_rad, periods, steps=4096):
    period = 2 * math.pi * math.sqrt(a ** 3 / MU)
    elements = [a * (1 - e) / 1000, e, math.radians(inclination_deg),
                math.radians(node_deg), math.radians(periapse_deg),
                mean_anomaly_rad, 0.0, MU / 1e9]
    state = [float(value) * 1000 for value in spice.conics(elements, 0.0)]
    parameters = _parameters(state, period * periods, steps)
    # prop2b accepts a coherent unit system; here everything is supplied in SI.
    expected = [list(map(float, spice.prop2b(MU, state, parameters["duration_s"] * i / steps)))
                for i in range(steps + 1)]
    try:
        comparison = _compare(parameters, expected, a, math.sqrt(MU / a))
        actual = comparison["actual"]
        passed = (actual["max_position_error_over_semimajor_axis"] <= STATE_RELATIVE_TOLERANCE
                  and actual["max_velocity_error_over_circular_speed"] <= STATE_RELATIVE_TOLERANCE
                  and max(actual["relative_metric_errors"].values()) <= METRIC_RELATIVE_TOLERANCE)
    except ValueError as error:
        comparison = {"expected": {"status": "completed", "metrics": _expected_metrics(expected)},
                      "actual": {"status": "rejected", "error": str(error)}}
        passed = False
    return {
        "id": name, "model": "orbital_trajectory",
        "source_urls": [PROP2B_URL, CONICS_URL, WRAPPER_URL],
        "reference_kind": "independent_external_software_CSPICE_universal_variables",
        "inputs": {"parameters": parameters, "constructed_elements": {
            "semimajor_axis_m": a, "eccentricity": e, "inclination_deg": inclination_deg,
            "ascending_node_deg": node_deg, "argument_of_periapse_deg": periapse_deg,
            "mean_anomaly_rad": mean_anomaly_rad, "duration_periods": periods}},
        **comparison,
        "tolerance": {"max_position_error_over_semimajor_axis": STATE_RELATIVE_TOLERANCE,
                      "max_velocity_error_over_circular_speed": STATE_RELATIVE_TOLERANCE,
                      "maximum_relative_sampled_metric_error": METRIC_RELATIVE_TOLERANCE},
        "passed": bool(passed),
        "reference_environment": {"spiceypy": spice.__version__, "toolkit": spice.tkvrsn("TOOLKIT")},
        "limitations": [
            "Synthetic elements and supplied Earth-like mu; no measured spacecraft or flight data.",
            "Compares one Newtonian point-mass two-body model with another implementation of the same physics.",
            "2% trajectory and 1% sampled-metric tolerances are benchmark levels, not mission suitability criteria.",
            "Sample extrema refer to the shared discrete grid; continuous-time extrema are not certified.",
            "No perturbations, thrust, atmosphere, collision/contact or real-vehicle applicability is validated.",
        ],
    }


def _circular_analytic():
    radius, inclination = 7_000_000.0, math.radians(55)
    speed = math.sqrt(MU / radius)
    period = 2 * math.pi * radius / speed
    state = [radius, 0.0, 0.0, 0.0, speed * math.cos(inclination), speed * math.sin(inclination)]
    grids = [1024, 2048, 4096]
    errors, records = [], []
    for steps in grids:
        parameters = _parameters(state, period, steps)
        expected = []
        for index in range(steps + 1):
            phase = 2 * math.pi * index / steps
            c, s = math.cos(phase), math.sin(phase)
            expected.append([radius * c, radius * s * math.cos(inclination), radius * s * math.sin(inclination),
                             -speed * s, speed * c * math.cos(inclination), speed * c * math.sin(inclination)])
        comparison = _compare(parameters, expected, radius, speed)
        errors.append(comparison["actual"]["max_position_error_m"])
        records.append({"steps": steps, **comparison["actual"]})
    orders = [math.log2(coarse / fine) for coarse, fine in zip(errors, errors[1:])]
    return {
        "id": "orbit_circular_analytic_refinement", "model": "orbital_trajectory",
        "source_urls": [PROP2B_URL],
        "reference_kind": "published_circular_solution_analytic_refinement",
        "inputs": {"mu_m3_s2": MU, "radius_m": radius, "inclination_deg": 55.0,
                   "duration_periods": 1.0, "steps": grids},
        "expected": {"second_order_interval": list(ORDER_INTERVAL),
                     "circular_radius_m": radius, "circular_speed_m_s": speed,
                     "final_state_m_and_m_s": state},
        "actual": {"refinement_orders": orders, "grids": records},
        "tolerance": {"order_min": ORDER_INTERVAL[0], "order_max": ORDER_INTERVAL[1],
                      "fine_max_position_error_over_radius": CIRCULAR_FINE_RELATIVE_TOLERANCE,
                      "fine_max_velocity_error_over_speed": CIRCULAR_FINE_RELATIVE_TOLERANCE},
        "passed": (all(ORDER_INTERVAL[0] <= order <= ORDER_INTERVAL[1] for order in orders)
                   and records[-1]["max_position_error_over_semimajor_axis"] <= CIRCULAR_FINE_RELATIVE_TOLERANCE
                   and records[-1]["max_velocity_error_over_circular_speed"] <= CIRCULAR_FINE_RELATIVE_TOLERANCE),
        "limitations": ["Analytic circular-orbit solution only; no external flight observations.",
                        "Expected second-order behavior is checked on these three grids, not proved for every input.",
                        "Inclination rotation is constructed here; it is not obtained from production orbital element extraction."],
    }


def run_checks():
    """Return independently sourced benchmark rows or raise a controlled dependency error."""
    spice = _spice()
    rows = [
        _reference_case(spice, "orbit_spice_circular_eight_periods", 7e6, 0.0, 55, 31, 17, 0.3, 8.0),
        _reference_case(spice, "orbit_spice_circular_seven_and_half_periods", 7e6, 0.0, 55, 31, 17, 0.3, 7.5),
        _reference_case(spice, "orbit_spice_inclined_eccentric_four_periods", 12e6, 0.25, 63, 114, 29, 0.4, 4.0),
        _reference_case(spice, "orbit_spice_eccentric_one_period", 20e6, 0.6, 32, 238, 73, 0.0, 1.0),
        _reference_case(spice, "orbit_spice_retrograde_eccentric", 30e6, 0.7, 137, 51, 211, 1.0, 0.75),
        _circular_analytic(),
    ]
    # Fixed duration, not recomputed from production-derived elements.
    refinement = [_reference_case(spice, f"orbit_spice_refinement_{steps}", 12e6, .25,
                                 63, 114, 29, .4, 1.0, steps) for steps in [1024, 2048, 4096]]
    errors = [row["actual"]["max_position_error_m"] for row in refinement]
    orders = [math.log2(coarse / fine) for coarse, fine in zip(errors, errors[1:])]
    rows.append({
        "id": "orbit_spice_eccentric_refinement", "model": "orbital_trajectory",
        "source_urls": [PROP2B_URL, CONICS_URL, WRAPPER_URL],
        "reference_kind": "independent_external_software_refinement",
        "inputs": {"constructed_elements": deepcopy(refinement[0]["inputs"]["constructed_elements"]),
                   "steps": [1024, 2048, 4096]},
        "expected": {"second_order_interval": list(ORDER_INTERVAL)},
        "actual": {"refinement_orders": orders, "grids": [
            {"steps": row["inputs"]["parameters"]["steps"], **row["actual"]} for row in refinement]},
        "tolerance": {"order_min": ORDER_INTERVAL[0], "order_max": ORDER_INTERVAL[1]},
        "passed": all(ORDER_INTERVAL[0] <= order <= ORDER_INTERVAL[1] for order in orders),
        "reference_environment": refinement[0]["reference_environment"],
        "limitations": refinement[0]["limitations"],
    })
    return rows


if __name__ == "__main__":
    checks = run_checks()
    print(json.dumps(checks, indent=2, allow_nan=False))
    raise SystemExit(0 if all(row["passed"] for row in checks) else 1)
