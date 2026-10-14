"""Constructed component-screening examples, not a real spacecraft design."""
from copy import deepcopy


def _input(value, unit):
    return {"value": value, "unit": unit, "source": "Constructed demonstration input; not measured hardware data."}


def example_projects():
    baseline = {
        "schema": "sixd.project.v1", "project_id": "constructed-engineering-change",
        "name": "Constructed engineering change review", "revision": "1",
        "description": "Four bounded component calculations. Inputs and limits are illustrative; no mission or physical model validity is established.",
        "lifecycle_stage": "design",
        "inputs": {
            "initial_mass": _input(1000, "kg"), "dry_mass": _input(500, "kg"),
            "delta_v": _input(1000, "m/s"), "specific_impulse": _input(300, "s"),
            "thrust": _input(200, "N"), "minimum_propellant_margin": _input(0, "kg"),
            "maximum_burn_duration": _input(6000, "s"), "mount_length": _input(0.2, "m"),
            "young_modulus": _input(70e9, "Pa"), "second_moment": _input(2e-6, "m^4"),
            "outer_fiber": _input(0.01, "m"), "maximum_bending_stress": _input(1e6, "Pa"),
            "maximum_tip_deflection": _input(0.001, "m"), "heat_input": _input(200, "W"),
            "radiator_area": _input(1, "m^2"), "emissivity": _input(0.8, "1"),
            "background_temperature": _input(3, "K"), "maximum_temperature": _input(320, "K"),
            "density": _input(0.01, "kg/m^3"), "relative_speed": _input(100, "m/s"),
            "drag_coefficient": _input(1, "1"), "reference_area": _input(1, "m^2"),
            "maximum_drag_force": _input(100, "N"),
        },
        "models": [
            {"id": "propulsion", "type": "ideal_propulsion", "inputs": {
                key: key for key in ("initial_mass", "dry_mass", "delta_v", "specific_impulse", "thrust")}},
            {"id": "mount", "type": "static_cantilever", "description": "Explicit ideal mapping: thrust magnitude is a transverse free-end load on this beam.", "inputs": {
                "tip_force": "thrust", "length": "mount_length", "young_modulus": "young_modulus",
                "second_moment": "second_moment", "outer_fiber": "outer_fiber"}},
            {"id": "thermal", "type": "radiative_equilibrium", "inputs": {
                "heat_input": "heat_input", "area": "radiator_area", "emissivity": "emissivity",
                "background_temperature": "background_temperature"}},
            {"id": "atmospheric_load", "type": "drag_load", "description": "Separate constructed atmospheric load case; it does not establish the orbital example's atmospheric applicability.", "inputs": {
                key: key for key in ("density", "relative_speed", "drag_coefficient", "reference_area")}},
        ],
        "requirements": [],
    }
    for identity, title, model, metric, operator, limit in (
        ("fuel_margin", "Nonnegative ideal propellant margin", "propulsion", "propellant_margin", ">=", "minimum_propellant_margin"),
        ("burn_duration", "Declared burn-duration limit", "propulsion", "burn_duration", "<=", "maximum_burn_duration"),
        ("mount_stress", "Declared static beam stress limit", "mount", "bending_stress", "<=", "maximum_bending_stress"),
        ("mount_deflection", "Declared beam deflection limit", "mount", "tip_deflection", "<=", "maximum_tip_deflection"),
        ("thermal_limit", "Declared steady equilibrium temperature limit", "thermal", "equilibrium_temperature", "<=", "maximum_temperature"),
        ("drag_limit", "Declared drag-force limit", "atmospheric_load", "drag_force", "<=", "maximum_drag_force"),
    ):
        baseline["requirements"].append({"id": identity, "title": title, "model_id": model,
            "metric": metric, "operator": operator, "limit_input": limit, "critical": True})
    revised = deepcopy(baseline)
    revised["revision"] = "2"
    revised["inputs"]["thrust"]["value"] = 400
    # Heat is explicitly supplied as a changed input; it is not inferred from thrust.
    revised["inputs"]["heat_input"]["value"] = 600
    missing = deepcopy(revised)
    missing["revision"] = "3"
    missing["inputs"]["maximum_tracking_error"] = _input(10, "m")
    missing["models"].append({"id": "control", "type": "unsupported_closed_loop_gnc", "inputs": {}})
    missing["requirements"].append({"id": "control_tracking", "title": "Unimplemented control-performance requirement",
        "model_id": "control", "metric": "tracking_error", "operator": "<=",
        "limit_input": "maximum_tracking_error", "critical": True})
    return {"baseline": baseline, "revised": revised, "missing_evidence": missing}
