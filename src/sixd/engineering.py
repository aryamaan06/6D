"""Maintained, bounded engineering calculations for explicit project inputs.

These adapters calculate consequences of supplied idealized models. Completion
does not validate the model's applicability, source data, or a complete vehicle.
All parameters require the exact SI unit below; no conversion or defaults occur.

References checked October 14, 2026 (Asia/Calcutta):
* NASA ideal rocket equation and specific impulse:
  https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/
  https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/
* MIT bending-stress and cantilever free-end-deflection derivations:
  https://web.mit.edu/course/3/3.11/www/modules/bstress.pdf
  https://ocw.mit.edu/courses/3-052-nanomechanics-of-materials-and-biomaterials-spring-2007/d8d2ffa0503ad0adf0edb741ddb4e4c8_lec2_appendix.pdf
* NASA spacecraft thermal balance and NIST Stefan-Boltzmann constant:
  https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/
  https://physics.nist.gov/cgi-bin/cuu/Value?sigma%7Csearch_for=stefan+boltzmann
* NASA drag equation and coefficient/reference-area conventions:
  https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/

The thermal equation specializes radiation to a grey surface viewing an
isothermal black environment with unit view factor and no other heat paths.
The coefficient is the NIST value rounded to ten significant digits. Propulsion
uses conventional standard gravity 9.80665 m/s^2 to interpret specific impulse;
this is not the vehicle's actual gravitational acceleration.
"""

from __future__ import annotations

import math
from typing import Any, Callable


STANDARD_GRAVITY = 9.80665
STEFAN_BOLTZMANN = 5.670374419e-8

MODEL_VERSIONS = {
    "ideal_propulsion": "1",
    "static_cantilever": "1",
    "radiative_equilibrium": "1",
    "drag_load": "1",
}

MODEL_PARAMETERS = {
    "ideal_propulsion": {
        "initial_mass": "kg", "dry_mass": "kg", "delta_v": "m/s",
        "specific_impulse": "s", "thrust": "N",
    },
    "static_cantilever": {
        "tip_force": "N", "length": "m", "young_modulus": "Pa",
        "second_moment": "m^4", "outer_fiber": "m",
    },
    "radiative_equilibrium": {
        "heat_input": "W", "area": "m^2", "emissivity": "1",
        "background_temperature": "K",
    },
    "drag_load": {
        "density": "kg/m^3", "relative_speed": "m/s",
        "drag_coefficient": "1", "reference_area": "m^2",
    },
}

_ASSUMPTIONS = {
    "ideal_propulsion": [
        "Single ideal burn with constant specific impulse and positive constant thrust magnitude.",
        "Initial mass includes dry mass and all available usable propellant; no staging or reserves.",
        "Delta-v is a nonnegative prescribed magnitude; gravity, drag and steering losses are omitted.",
        "Burn duration is the theoretical required duration, even when available propellant is insufficient.",
    ],
    "static_cantilever": [
        "Uniform slender Euler-Bernoulli beam with a rigid clamp and a transverse point load at its free end.",
        "Tip force is a nonnegative load magnitude; outputs are maximum bending-stress and tip-deflection magnitudes.",
        "Small deflection, linear elasticity, constant modulus and section moment about the loaded bending axis.",
    ],
    "radiative_equilibrium": [
        "One isothermal grey emitting surface in steady radiative equilibrium.",
        "The entire emitting area views an isothermal black background with unit view factor.",
        "Heat input is externally supplied total nonnegative absorbed/generated power, excluding background radiation.",
        "Constant infrared emissivity; radiation is the only heat-loss path.",
    ],
    "drag_load": [
        "Density, nonnegative speed relative to the atmosphere and drag coefficient are supplied for one condition.",
        "Drag coefficient and reference area must use the same area convention and applicable flow conditions.",
        "Drag is a force magnitude opposing the relative flow; no force-vector or structural-load mapping is inferred.",
    ],
}

_NOT_ASSESSED = {
    "ideal_propulsion": [
        "Source-data accuracy, actual engine performance, feed system, tank qualification and propellant reserves.",
        "Flight trajectory, gravity/drag/steering losses, staging and GNC execution of the maneuver.",
    ],
    "static_cantilever": [
        "Whether geometry, materials, boundary conditions and deflection satisfy the assumed beam regime.",
        "Yield allowable and safety factors unless independently declared as project requirements.",
        "Shear deformation/stress, buckling, fatigue, vibration, joints, distributed loads and whole-vehicle integrity.",
    ],
    "radiative_equilibrium": [
        "Transient heating, heat capacity, temperature gradients, conduction, convection and actual view factors.",
        "Heat-input provenance, material/coating behavior and temperature-dependent emissivity.",
        "Aerothermodynamic heating prediction; a supplied heat load is not independently validated.",
    ],
    "drag_load": [
        "Coefficient applicability not independently verified; a source label is not validation of the flow regime.",
        "Reference-area compatibility, atmospheric data, Mach/Reynolds/Knudsen regime and attitude require external evidence.",
        "Lift, moments, aerodynamic stability, CFD, trajectory, aeroheating and structural load distribution.",
    ],
}


def _finite(value: float, description: str, *, positive: bool = False) -> float:
    if not math.isfinite(value) or (positive and value <= 0):
        raise ArithmeticError(f"{description} is outside the finite numerical range.")
    return value


def _positive(parameters: dict[str, float], *names: str) -> None:
    for name in names:
        if parameters[name] <= 0:
            raise ValueError(f"{name} must be greater than zero.")


def _nonnegative(parameters: dict[str, float], *names: str) -> None:
    for name in names:
        if parameters[name] < 0:
            raise ValueError(f"{name} must be a nonnegative magnitude.")


def _propulsion(p: dict[str, float]) -> dict[str, tuple[float, str]]:
    """ve=g0*Isp; required=m0*(1-exp(-dv/ve)); flow=thrust/ve.

    Available=m0-dry_mass; margin=m0*exp(-dv/ve)-dry_mass;
    duration=required/flow.
    A negative margin is a meaningful shortage, not an invalid calculation.
    """
    _positive(p, "initial_mass", "dry_mass", "specific_impulse", "thrust")
    _nonnegative(p, "delta_v")
    if p["dry_mass"] > p["initial_mass"]:
        raise ValueError("dry_mass cannot exceed initial_mass.")
    exhaust_speed = _finite(STANDARD_GRAVITY * p["specific_impulse"], "Effective exhaust speed", positive=True)
    exponent = _finite(p["delta_v"] / exhaust_speed, "Delta-v/exhaust-speed ratio")
    # expm1 preserves meaningful small burns lost by subtracting exp(-x) from 1.
    required = _finite(-p["initial_mass"] * math.expm1(-exponent), "Required propellant")
    if p["delta_v"] > 0 and required == 0:
        raise ArithmeticError("Required propellant underflows the numerical range.")
    available = p["initial_mass"] - p["dry_mass"]
    if exponent <= 0.5:
        # Equivalent to remaining final mass minus dry mass, without first
        # rounding a tiny burn away from a large initial mass. fsum also keeps
        # the dry-mass term when the other terms differ greatly in magnitude.
        margin = math.fsum((p["initial_mass"], -required, -p["dry_mass"]))
    else:
        # For long burns, required propellant can round up to the entire initial
        # mass. Never derive the remaining mass by subtracting that rounded
        # requirement. Logs also avoid exp(-x) underflow before multiplication
        # when a large initial mass leaves a representable final mass.
        remaining_mass = _finite(math.exp(math.log(p["initial_mass"]) - exponent),
                                 "Remaining final mass", positive=True)
        margin = remaining_mass - p["dry_mass"]
    margin = _finite(margin, "Propellant margin")
    mass_flow = _finite(p["thrust"] / exhaust_speed, "Mass flow", positive=True)
    duration = _finite(required / mass_flow, "Required burn duration", positive=required > 0)
    return {
        "propellant_required": (required, "kg"),
        "propellant_available": (available, "kg"),
        "propellant_margin": (margin, "kg"),
        "mass_flow": (mass_flow, "kg/s"),
        "burn_duration": (duration, "s"),
    }


def _cantilever(p: dict[str, float]) -> dict[str, tuple[float, str]]:
    """Magnitudes at clamp/tip: stress=F*L*c/I; deflection=F*L^3/(3*E*I)."""
    _positive(p, "length", "young_modulus", "second_moment", "outer_fiber")
    _nonnegative(p, "tip_force")
    if p["tip_force"] == 0:
        return {"bending_stress": (0.0, "Pa"), "tip_deflection": (0.0, "m")}
    moment = _finite(p["tip_force"] * p["length"], "Clamp bending moment", positive=True)
    numerator = _finite(moment * p["outer_fiber"], "Bending-stress numerator", positive=True)
    stress = _finite(numerator / p["second_moment"], "Bending stress", positive=True)
    length_squared = _finite(p["length"] * p["length"], "Squared beam length", positive=True)
    numerator = _finite(moment * length_squared, "Deflection numerator", positive=True)
    stiffness = _finite(p["young_modulus"] * p["second_moment"], "Flexural rigidity", positive=True)
    deflection = _finite((numerator / stiffness) / 3.0, "Tip deflection", positive=True)
    return {"bending_stress": (stress, "Pa"), "tip_deflection": (deflection, "m")}


def _radiative(p: dict[str, float]) -> dict[str, tuple[float, str]]:
    """Q=epsilon*sigma*A*(T^4-Tbackground^4); solve nonnegative steady T."""
    _positive(p, "area", "emissivity")
    _nonnegative(p, "heat_input", "background_temperature")
    if p["emissivity"] > 1:
        raise ValueError("emissivity must be at most one.")
    if p["heat_input"] == 0:
        return {"equilibrium_temperature": (p["background_temperature"], "K")}
    # Compute the fourth-root power term in logs, so valid final temperatures
    # do not fail merely because an intermediate fourth power overflows.
    log_power_term = (math.log(p["heat_input"]) - math.log(p["emissivity"])
                      - math.log(STEFAN_BOLTZMANN) - math.log(p["area"])) / 4.0
    radiation_temperature = _finite(math.exp(log_power_term), "Radiation temperature", positive=True)
    scale = max(p["background_temperature"], radiation_temperature)
    factor = ((p["background_temperature"] / scale) ** 4
              + (radiation_temperature / scale) ** 4) ** 0.25
    temperature = _finite(scale * factor, "Equilibrium temperature", positive=True)
    return {"equilibrium_temperature": (temperature, "K")}


def _drag(p: dict[str, float]) -> dict[str, tuple[float, str]]:
    """Single-condition magnitudes: q=rho*vrelative^2/2; drag=q*Cd*Aref."""
    _positive(p, "reference_area")
    _nonnegative(p, "density", "relative_speed", "drag_coefficient")
    if p["density"] == 0 or p["relative_speed"] == 0:
        return {"dynamic_pressure": (0.0, "Pa"), "drag_force": (0.0, "N")}
    speed_squared = _finite(p["relative_speed"] * p["relative_speed"], "Squared relative speed", positive=True)
    pressure = _finite((p["density"] * speed_squared) / 2.0, "Dynamic pressure", positive=True)
    if p["drag_coefficient"] == 0:
        drag = 0.0
    else:
        area_coefficient = _finite(p["reference_area"] * p["drag_coefficient"], "Area/coefficient product", positive=True)
        drag = _finite(pressure * area_coefficient, "Drag force", positive=True)
    return {"dynamic_pressure": (pressure, "Pa"), "drag_force": (drag, "N")}


_CALCULATORS: dict[str, Callable[[dict[str, float]], dict[str, tuple[float, str]]]] = {
    "ideal_propulsion": _propulsion,
    "static_cantilever": _cantilever,
    "radiative_equilibrium": _radiative,
    "drag_load": _drag,
}


def _bind_inputs(project: dict[str, Any], model: dict[str, Any]) -> dict[str, float]:
    expected = MODEL_PARAMETERS[model["type"]]
    bindings = model.get("inputs")
    if not isinstance(bindings, dict):
        raise ValueError("Model input bindings must be an object.")
    if set(bindings) != set(expected):
        missing = sorted(set(expected) - set(bindings))
        extra = sorted(str(key) for key in set(bindings) - set(expected))
        raise ValueError(f"Exact parameter bindings required; missing={missing}, unexpected={extra}.")
    values = {}
    for parameter, unit in expected.items():
        input_id = bindings[parameter]
        if not isinstance(input_id, str) or input_id not in project["inputs"]:
            raise ValueError(f"{parameter} must reference an existing project input.")
        record = project["inputs"][input_id]
        if not isinstance(record, dict) or set(record) != {"value", "unit", "source"}:
            raise ValueError(f"{parameter} requires exactly value, unit and source fields.")
        if record["unit"] != unit:
            raise ValueError(f"{parameter} requires unit {unit}; no conversion is performed.")
        if not isinstance(record["source"], str) or not record["source"].strip():
            raise ValueError(f"{parameter} requires a nonempty source label.")
        value = record["value"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{parameter} must be a finite number, not a boolean or string.")
        try:
            numeric_value = float(value)
        except (OverflowError, ValueError):
            raise ValueError(f"{parameter} is outside the finite numerical range.") from None
        if not math.isfinite(numeric_value):
            raise ValueError(f"{parameter} must be a finite number.")
        values[parameter] = numeric_value
    return values


def evaluate_models(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Calculate supported models without mutating the project or running AI.

    Callers normally use lifecycle.validate_project first. Invalid adapter
    parameters abstain individually with empty metrics, preserving other models.
    Malformed top-level containers or duplicate model IDs raise ValueError.
    """
    if not isinstance(project, dict) or not isinstance(project.get("inputs"), dict) or not isinstance(project.get("models"), list):
        raise ValueError("A project requires an inputs object and a models list.")
    results = {}
    for model in project["models"]:
        if (not isinstance(model, dict) or not isinstance(model.get("id"), str)
                or not model["id"].strip() or not isinstance(model.get("type"), str)
                or not model["type"].strip()):
            raise ValueError("Every model requires nonempty string id and type.")
        model_id, model_type = model["id"], model["type"]
        if model_id in results:
            raise ValueError(f"Duplicate model ID: {model_id}.")
        result = {
            "model_id": model_id, "model_type": model_type,
            "model_version": MODEL_VERSIONS.get(model_type),
            "status": "not_assessed", "metrics": {},
            "assumptions": list(_ASSUMPTIONS.get(model_type, [])),
            "not_assessed": list(_NOT_ASSESSED.get(model_type, [])), "issues": [],
        }
        if model_type not in _CALCULATORS:
            result["not_assessed"] = [f"No maintained deterministic adapter supports model type {model_type}."]
            result["issues"] = ["Unsupported model type; no quantitative result was produced."]
        else:
            try:
                parameters = _bind_inputs(project, model)
                metrics = _CALCULATORS[model_type](parameters)
                result["metrics"] = {
                    name: {"value": _finite(value, name), "unit": unit}
                    for name, (value, unit) in metrics.items()
                }
                result["status"] = "completed"
            except (ValueError, ArithmeticError) as exc:
                result["status"] = "invalid_inputs"
                result["metrics"] = {}
                result["issues"] = [str(exc)]
        results[model_id] = result
    return results
