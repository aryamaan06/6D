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
* NASA spacecraft electrical-power subsystem context and NIST power units:
  https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
  https://www.nist.gov/glossary-term/34606

The thermal equation specializes radiation to a grey surface viewing an
isothermal black environment with unit view factor and no other heat paths.
The coefficient is the NIST value rounded to ten significant digits. Propulsion
uses conventional standard gravity 9.80665 m/s^2 to interpret specific impulse;
this is not the vehicle's actual gravitational acceleration.
The power adapter is only accounting of declared bus loads/generation and
upfront usable energy; the electrical-power reference does not validate any
supplied equipment, battery, operating profile or the conservative no-recharge
policy. A watt-second is a joule.
"""

from __future__ import annotations

import math
import json
import re
from fractions import Fraction
from typing import Any, Callable

from . import orbital_adapter, attitude, powered_flight, guided_ascent, staged_ascent


STANDARD_GRAVITY = 9.80665
STEFAN_BOLTZMANN = 5.670374419e-8

MODEL_VERSIONS = {
    "staged_ascent": "1",
    "guided_ascent": "1",
    "powered_flight": "2",
    "attitude_control": "1",
    "ideal_propulsion": "1",
    "static_cantilever": "1",
    "radiative_equilibrium": "1",
    "drag_load": "1",
    "orbital_trajectory": "3",
    "power_energy_budget": "1",
}

MODEL_PARAMETERS = {
    "staged_ascent": dict(staged_ascent.PARAMETERS),
    "guided_ascent": dict(guided_ascent.PARAMETERS),
    "powered_flight": dict(powered_flight.PARAMETERS),
    "attitude_control": dict(attitude.PARAMETERS),
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
    "orbital_trajectory": dict(orbital_adapter.PARAMETERS),
    # Modes/load rows use dynamic parameter roles; power_parameters validates
    # their exact layout rather than treating this global subset as sufficient.
    "power_energy_budget": {
        "usable_battery_energy": "J", "max_battery_power": "W", "bus_power_limit": "W",
    },
}

_ASSUMPTIONS = {
    "staged_ascent": list(staged_ascent.ASSUMPTIONS),
    "guided_ascent": list(guided_ascent.ASSUMPTIONS),
    "powered_flight": list(powered_flight.ASSUMPTIONS),
    "attitude_control": list(attitude.ASSUMPTIONS),
    "power_energy_budget": [
        "Explicit sequential operating modes; all listed equipment runs continuously and simultaneously throughout its mode.",
        "Generation and equipment power are supplied constant bus-level values for each mode; integer counts multiply equipment demand.",
        "Usable battery energy is supplied upfront as bus-deliverable energy after user-declared reserves and losses; no additional reserve or efficiency is inferred.",
        "Only generation shortfall draws this energy budget; surplus generation receives no charging or recharge credit.",
        "Remaining energy budget may be negative to identify a shortfall; it is not battery state of charge or a simulated battery state.",
        "Power-capacity margins and total usable-energy margin are independent checks; this budget is not a validated electrical-system model.",
    ],
    "orbital_trajectory": list(orbital_adapter.ASSUMPTIONS),
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
    "staged_ascent": list(staged_ascent.NOT_ASSESSED),
    "guided_ascent": list(guided_ascent.NOT_ASSESSED),
    "powered_flight": list(powered_flight.NOT_ASSESSED),
    "attitude_control": list(attitude.NOT_ASSESSED),
    "power_energy_budget": [
        "Accuracy, completeness, measurement convention and applicability of supplied loads, generation, capacities, reserves and losses.",
        "Solar illumination, eclipse geometry, panel pointing, solar-array sizing, degradation and generation prediction.",
        "Charging, recharge, battery chemistry, voltage, state of charge, temperature, capacity degradation and discharge-efficiency prediction.",
        "Inrush, transients, voltage/current limits, wiring losses, conversion electronics, protection and fault response.",
        "Duty cycles, load scheduling within a mode, overlapping modes, load shedding and automatic operations planning.",
        "Whole-vehicle readiness, environmental qualification, hardware validation and mission success.",
    ],
    "orbital_trajectory": list(orbital_adapter.NOT_ASSESSED),
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


def model_applicability(model_type):
    """Reference context, never a claim of validation for supplied hardware."""
    entries = {
        "staged_ascent": (
            "Planar ascent with declared piecewise-linear thrust profiles and serial stages, analytical propellant depletion and ideal dry-mass jettison.",
            "Contiguous bounded stage/profile layouts, immediate liftoff, exact fuel/schedule/separation/ignition boundaries and three-grid vector-state agreement; sampled criteria only.",
            "Engine/profile applicability, separation dynamics or impulse, upper-stage ignition reliability, attitude, closed-loop guidance, variable aerodynamic geometry, aeroheating and landing.",
            "NASA specific impulse and ideal rocket equation", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/",
            "Constructed constant-engine reductions, ideal multi-stage velocity increments and separately integrated profile cases. Ideal mass jettison does not validate real separation."),
        "guided_ascent": (
            "Planar constant-thrust ascent and above-surface coast with an explicit local-radial pitch programme, analytical mass, central gravity and vector drag.",
            "Immediate radial liftoff, bounded pitch/time/grid/domain, exact schedule/cutoff segmentation and three-grid vector-state agreement; sampled metrics only.",
            "Steering programme and thrust/atmosphere applicability, closed-loop guidance, navigation, stability, winds, lift, staging, aeroheating and landing.",
            "NASA rocket flight and drag equations", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/",
            "Constructed analytical vertical-vacuum reduction and separately integrated planar reference cases; a prescribed pitch programme does not validate launch GNC."),
        "powered_flight": (
            "Vertical constant-thrust ascent and above-surface coast; analytical mass, radial gravity and exponential-atmosphere drag.",
            "Immediate liftoff, positive propellant, bounded time/grid/domain and three-grid state agreement; sampled metrics only.",
            "Engine and atmosphere applicability, coefficient/area convention, winds, steering, staging, aeroheating and landing.",
            "NASA rocket flight equations and drag", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/",
            "Constructed analytical vacuum and separately integrated atmospheric reference cases; no flight qualification."),
        "ideal_propulsion": (
            "Single ideal constant-Isp burn; no flight-loss prediction.",
            "Positive masses, Isp and thrust; nonnegative prescribed delta-v; finite results.",
            "Engine performance, reserves, staging and gravity/drag/steering losses.",
            "NASA ideal rocket equation", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/",
            "Rounded published illustration and independent equation arithmetic."),
        "static_cantilever": (
            "Uniform slender linear-elastic beam, rigid clamp and transverse free-end point load.",
            "Positive section/stiffness/length inputs and nonnegative force magnitude.",
            "Small-deflection regime, actual support/load geometry, material allowables and section validity.",
            "MIT beam stress derivation", "https://web.mit.edu/course/3/3.11/www/modules/bstress.pdf",
            "Published equations with constructed geometry; no matching hardware example."),
        "radiative_equilibrium": (
            "Steady isothermal grey surface viewing a black environment with unit view factor.",
            "Positive area and emissivity; emissivity at most one; nonnegative heat and background temperature.",
            "Equilibrium, real view factors, gradients, other heat paths and coating/load applicability.",
            "NASA spacecraft thermal control", "https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/",
            "Published radiative relation with constructed finite-background arithmetic."),
        "drag_load": (
            "Drag magnitude for one supplied atmospheric condition and area convention.",
            "Positive reference area; nonnegative density, speed and coefficient; finite results.",
            "Coefficient/area compatibility, Mach/Reynolds regime, attitude, environment and distributed loading.",
            "NASA drag equation", "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/",
            "Rounded Smeaton illustration and an independently evaluated constructed case."),
        "orbital_trajectory": (
            "Unforced elliptic point-mass two-body translation; sampled position/radius/speed only.",
            "Elliptic domain, clearance, window and step limits; v3 uses RK4 with explicit three-grid agreement criteria; retained v2 uses Velocity Verlet.",
            "Appropriate forces/frame/initial data, perturbations, continuous-time limits and mission accuracy.",
            "NASA NAIF two-body reference", "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/prop2b_c.html",
            "External CSPICE comparisons and constructed refinement cases; long-run phase errors remain material."),
        "power_energy_budget": (
            "Sequential constant-load modes with upfront usable battery energy and no recharge credit.",
            "Finite nonnegative capacities/loads/generation, positive durations and whole equipment counts.",
            "Measured loads and derating, solar geometry, battery SOC/charging, transients and qualification.",
            "OpenStax electrical energy and power", "https://openstax.org/books/university-physics-volume-2/pages/9-5-electrical-energy-and-power",
            "Published energy totals and an independently summed constructed operating schedule."),
        "attitude_control": (
            "Single rigid principal axis with fixed-target continuous PD control and clipped ideal torque.",
            "Positive inertia/duration/tolerances, finite bounded grids and coarse/fine agreement.",
            "Inertia/actuator applicability, sensors, delays, uncertainty, other axes and general switching accuracy.",
            "MIT differential equations course", "https://ocw.mit.edu/courses/18-03sc-differential-equations-fall-2011/",
            "Two published damped-oscillator solutions and constructed disturbance/clipping cases."),
    }
    if model_type not in entries:
        return None
    scope, check, external, title, url, note = entries[model_type]
    return {"schema": "sixd.model-applicability.v1", "physical_applicability": "not_assessed",
            "scope": scope, "checks": [check], "requires_external_evidence": [external],
            "references": [{"title": title, "url": url, "kind": "bounded_reference_context", "note": note}],
            "reference_disclosure": "Reference checks cover selected idealized cases, not this design. Numerical agreement does not establish physical applicability."}


def evidence_accuracy_gap(result):
    """Block new orbital evidence without rewriting version-one history."""
    if result.get("model_type") in {"powered_flight", "guided_ascent", "staged_ascent"} and result.get("status") == "completed":
        key = {"staged_ascent":"staged_response", "guided_ascent":"guided_response", "powered_flight":"flight_response"}[result["model_type"]]
        diagnostic = (result.get(key) or {}).get("diagnostics", {})
        if diagnostic.get("grid_agreement_met") is True:
            return None
        return {"status": "insufficient_accuracy", "reason": diagnostic.get("reason") or "Powered-flight grid agreement is unavailable."}
    if result.get("model_type") != "orbital_trajectory" or result.get("model_version") not in {"2", "3"}:
        return None
    accuracy = result.get("numerical_accuracy") or {}
    if accuracy.get("status") == "supported":
        return None
    return {"status": "insufficient_accuracy" if accuracy.get("status") == "insufficient_accuracy" else "accuracy_not_assessed",
            "reason": accuracy.get("reason") or "No declared numerical accuracy assessment supports this orbital result."}


def requirement_accuracy_gap(result, requirement, metric, limit):
    """Apply the supplied allowance to criteria, without calling it an error bound."""
    gap = evidence_accuracy_gap(result)
    if gap is not None:
        return gap
    if result.get("model_type") in {"powered_flight", "guided_ascent", "staged_ascent"}:
        adapter, key = {"staged_ascent":(staged_ascent,"staged_response"), "guided_ascent":(guided_ascent,"guided_response"), "powered_flight":(powered_flight,"flight_response")}[result["model_type"]]
        allowance = adapter.metric_allowance(result[key], requirement["metric"])
        if allowance == 0 and requirement["metric"] in {"burn_duration", "propellant_consumed", "initial_mass", "final_mass", "total_duration", "jettisoned_mass"}:
            return None
    elif result.get("model_type") == "orbital_trajectory" and result.get("model_version") in {"2", "3"}:
        criteria = result["numerical_accuracy"]["criteria"]
        allowance = criteria["position_tolerance_m" if metric["unit"] == "m" else "velocity_tolerance_m_s"]
    else:
        return None
    value, threshold, operator = metric["value"], limit["value"], requirement["operator"]
    # Exact Fraction comparisons avoid overflow and accidental rounding of a
    # near-limit allowance away from a much larger criterion value.
    distance = Fraction(value) - Fraction(threshold)
    overlaps = operator == "==" or (abs(distance) < Fraction(allowance)) or (distance == 0)
    # At the allowance boundary, an inequality can be proved only on its
    # inclusive passing side; the violating side still includes equality.
    if abs(distance) == Fraction(allowance):
        overlaps = (operator == "<=" and distance > 0) or (operator == ">=" and distance < 0) or operator == "=="
    if overlaps:
        return {"status": "insufficient_accuracy", "reason": "The declared numerical allowance overlaps this criterion. Refine the grid and justify a tighter allowance, or revise the criterion; an exact equality is not established by a finite-resolution trajectory."}
    return None


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


_POWER_ROLE = re.compile(
    r"mode\.([1-9][0-9]?)\.([a-zA-Z][a-zA-Z0-9_-]{0,31})\."
    r"(duration|generation|load\.([a-zA-Z][a-zA-Z0-9_-]{0,31})\.(power|count))\Z")
_POWER_RESERVED_IDS = {"constructor", "prototype", "__proto__"}


def power_parameters(bindings: dict[str, Any]) -> dict[str, str]:
    """Validate the v1 dynamic role layout and return every exact SI unit.

    Values may be input IDs or placeholders: this checks only role structure,
    not values or project inputs. Mode order is its explicit contiguous index;
    row/order insertion in a JSON object has no semantic effect.
    """
    if not isinstance(bindings, dict) or any(not isinstance(role, str) for role in bindings):
        raise ValueError("Power budget input bindings must be an object with string role names.")
    expected = dict(MODEL_PARAMETERS["power_energy_budget"])
    if not set(expected).issubset(bindings):
        raise ValueError("Power budget requires usable_battery_energy, max_battery_power and bus_power_limit bindings.")
    modes: dict[int, dict[str, Any]] = {}
    for role in bindings:
        if role in expected:
            continue
        match = _POWER_ROLE.fullmatch(role)
        if match is None:
            raise ValueError(f"Invalid power budget mode/load role: {role}.")
        raw_index, mode_id, field, load_id, load_field = match.groups()
        index = int(raw_index)
        if index > 16:
            raise ValueError("Power budget supports at most 16 sequential modes.")
        if mode_id in _POWER_RESERVED_IDS or load_id in _POWER_RESERVED_IDS:
            raise ValueError("Power budget mode/load IDs cannot use reserved object property names.")
        mode = modes.setdefault(index, {"id": mode_id, "fields": set(), "loads": {}})
        if mode["id"] != mode_id:
            raise ValueError("Each power budget mode index must have exactly one mode ID.")
        if load_id is None:
            mode["fields"].add(field)
            expected[role] = "s" if field == "duration" else "W"
        else:
            mode["loads"].setdefault(load_id, set()).add(load_field)
            expected[role] = "1" if load_field == "count" else "W"
    if not modes or set(modes) != set(range(1, len(modes) + 1)):
        raise ValueError("Power budget requires 1 to 16 modes with contiguous indices beginning at 1.")
    if len({mode["id"] for mode in modes.values()}) != len(modes):
        raise ValueError("Power budget mode IDs must be unique.")
    total_loads = 0
    for mode in modes.values():
        if mode["fields"] != {"duration", "generation"}:
            raise ValueError("Each power budget mode requires duration and generation bindings.")
        if not mode["loads"] or any(fields != {"power", "count"} for fields in mode["loads"].values()):
            raise ValueError("Each power budget mode requires equipment rows with both power and count bindings.")
        total_loads += len(mode["loads"])
    if total_loads > 128:
        raise ValueError("Power budget supports at most 128 equipment rows across all modes.")
    return expected


def _power_float(value: Fraction, description: str) -> float:
    """Round one exact bounded-budget result, never a nonzero value to zero."""
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ArithmeticError(f"{description} is outside the finite numerical range.") from None
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ArithmeticError(f"{description} overflows or underflows the finite numerical range.")
    return result


def _power_budget(parameters: dict[str, float]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Sum a piecewise constant bus budget; never infer charging or SOC.

    Exact rational accumulation preserves a small shortfall beside large
    supplied values. Float outputs are rounded only after each complete sum or
    difference; no capacity verdict is based on rounded intermediate totals.
    The rational values describe the supplied numeric inputs, not their physical
    uncertainty or accuracy. This is bounded arithmetic, not time integration.
    """
    units = power_parameters(parameters)
    p: dict[str, Fraction] = {}
    for role in units:
        value = parameters[role]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{role} must be a finite number, not a boolean or string.")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"{role} must be a finite number.")
        p[role] = Fraction(value)
        if p[role] < 0:
            raise ValueError(f"{role} must be a nonnegative magnitude.")
        if role.endswith(".duration") and p[role] <= 0:
            raise ValueError(f"{role} must be greater than zero.")
        if role.endswith(".count") and (p[role].denominator != 1 or p[role] > 1_000_000):
            raise ValueError(f"{role} must be an integer count from 0 to 1000000.")
    battery_energy = p["usable_battery_energy"]
    max_battery_power = p["max_battery_power"]
    bus_limit = p["bus_power_limit"]
    descriptions = sorted({(int(role.split(".")[1]), role.split(".")[2])
                           for role in units if role.startswith("mode.")})
    mode_rows = []
    elapsed = Fraction(0)
    cumulative = Fraction(0)
    load_energy_total = Fraction(0)
    generated_energy_total = Fraction(0)
    surplus_energy_total = Fraction(0)
    loads_by_mode, power_margins, generation_margins, bus_margins, battery_margins, deficits = ([] for _ in range(6))
    for index, mode_id in descriptions:
        prefix = f"mode.{index}.{mode_id}."
        duration = p[prefix + "duration"]
        generation = p[prefix + "generation"]
        load_ids = sorted({role[len(prefix + "load."):].split(".")[0]
                           for role in units if role.startswith(prefix + "load.")})
        load_rows = []
        load_power = Fraction(0)
        for load_id in load_ids:
            load_prefix = prefix + f"load.{load_id}."
            power = p[load_prefix + "power"]
            count = int(p[load_prefix + "count"])
            demand = power * count
            load_power += demand
            load_rows.append({"id": load_id, "power_w": _power_float(power, "Equipment power"),
                              "count": count, "load_power_w": _power_float(demand, "Equipment demand")})
        generation_margin = generation - load_power
        deficit = max(-generation_margin, Fraction(0))
        surplus = max(generation_margin, Fraction(0))
        bus_margin = bus_limit - load_power
        battery_margin = max_battery_power - deficit
        # For excess generation, generation+capacity-load is larger than
        # battery capability alone. Keep the declared combined power margin
        # exactly, while the independent battery-rate metric uses deficit.
        margin = min(bus_margin, generation + max_battery_power - load_power)
        load_energy = load_power * duration
        generated_energy = generation * duration
        required_energy = deficit * duration
        surplus_energy = surplus * duration
        cumulative += required_energy
        end = elapsed + duration
        start_float = _power_float(elapsed, "Mode start")
        end_float = _power_float(end, "Mode end")
        if end_float <= start_float:
            raise ArithmeticError("Mode duration is too small to retain distinct finite timeline endpoints.")
        mode_rows.append({
            "index": index, "id": mode_id, "start_s": start_float, "end_s": end_float,
            "duration_s": _power_float(duration, "Mode duration"),
            "generation_power_w": _power_float(generation, "Generation power"),
            "load_power_w": _power_float(load_power, "Mode equipment demand"),
            "battery_power_required_w": _power_float(deficit, "Battery power required"),
            "bus_power_margin_w": _power_float(bus_margin, "Bus power margin"),
            "battery_power_margin_w": _power_float(battery_margin, "Battery power margin"),
            "power_margin_w": _power_float(margin, "Power margin"),
            "load_energy_j": _power_float(load_energy, "Mode load energy"),
            "generated_energy_j": _power_float(generated_energy, "Mode generated energy"),
            "battery_energy_required_j": _power_float(required_energy, "Mode battery energy required"),
            "surplus_energy_j": _power_float(surplus_energy, "Mode surplus generation energy"),
            "cumulative_battery_energy_required_j": _power_float(cumulative, "Cumulative battery energy required"),
            "remaining_energy_budget_j": _power_float(battery_energy - cumulative, "Remaining energy budget"),
            "loads": load_rows,
        })
        elapsed = end
        load_energy_total += load_energy
        generated_energy_total += generated_energy
        surplus_energy_total += surplus_energy
        loads_by_mode.append(load_power)
        power_margins.append(margin)
        generation_margins.append(generation_margin)
        bus_margins.append(bus_margin)
        battery_margins.append(battery_margin)
        deficits.append(deficit)
    values = {
        "peak_load_power": (max(loads_by_mode), "W"),
        "minimum_power_margin": (min(power_margins), "W"),
        "total_load_energy": (load_energy_total, "J"),
        "total_generated_energy": (generated_energy_total, "J"),
        "battery_energy_required": (cumulative, "J"),
        "battery_energy_margin": (battery_energy - cumulative, "J"),
        "minimum_generation_margin": (min(generation_margins), "W"),
        "max_battery_power_required": (max(deficits), "W"),
        "minimum_bus_power_margin": (min(bus_margins), "W"),
        "minimum_battery_power_margin": (min(battery_margins), "W"),
        "total_duration": (elapsed, "s"),
        "surplus_generation_energy": (surplus_energy_total, "J"),
    }
    metrics = {name: {"value": _power_float(value, name), "unit": unit}
               for name, (value, unit) in values.items()}
    artifact = {
        "schema": "sixd.power-energy-budget.v1", "modes": mode_rows,
        "limits": {"usable_battery_energy_j": _power_float(battery_energy, "Usable battery energy"),
                   "max_battery_power_w": _power_float(max_battery_power, "Battery power capacity"),
                   "bus_power_limit_w": _power_float(bus_limit, "Bus power limit")},
        "assumptions": list(_ASSUMPTIONS["power_energy_budget"]),
        "not_assessed": list(_NOT_ASSESSED["power_energy_budget"]),
    }
    return metrics, artifact


def verify_power_artifact(artifact: Any, metrics: Any, project: dict[str, Any], model: dict[str, Any]) -> bool:
    """Verify retained v1 budget arithmetic from the exact recorded inputs.

    This never calls evaluate_models, runs a simulation, or authenticates a
    hardware test. Strict canonical JSON comparison rejects extra/missing
    fields, reordered mode/load rows, nonfinite values and boolean aliases.
    """
    if not isinstance(model, dict) or model.get("type") != "power_energy_budget":
        raise ValueError("Power budget artifact requires its recorded power model.")
    expected_metrics, expected_artifact = _power_budget(_bind_inputs(project, model))
    try:
        encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if encode(artifact) != encode(expected_artifact) or encode(metrics) != encode(expected_metrics):
            raise ValueError("Power budget artifact or metrics disagree with the recorded mode inputs and bounded arithmetic.")
    except (TypeError, OverflowError):
        raise ValueError("Power budget artifact must contain exact finite v1 JSON evidence.") from None
    return True


_CALCULATORS: dict[str, Callable[[dict[str, float]], dict[str, tuple[float, str]]]] = {
    "ideal_propulsion": _propulsion,
    "static_cantilever": _cantilever,
    "radiative_equilibrium": _radiative,
    "drag_load": _drag,
}


def _bind_inputs(project: dict[str, Any], model: dict[str, Any]) -> dict[str, float]:
    bindings = model.get("inputs")
    if not isinstance(bindings, dict):
        raise ValueError("Model input bindings must be an object.")
    expected = (power_parameters(bindings) if model["type"] == "power_energy_budget" else
                staged_ascent.parameter_units(bindings) if model["type"] == "staged_ascent" else MODEL_PARAMETERS[model["type"]])
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
        # Preserve finite integer operands for the budget's cancellation-safe
        # arithmetic. Other maintained adapters retain their established floats.
        values[parameter] = value if model["type"] == "power_energy_budget" else numeric_value
    return values


def evaluate_model(project: dict[str, Any], model: dict[str, Any], prior_results: dict[str, Any]) -> dict[str, Any]:
    """Execute one model using its current topologically preceding results."""
    model_id, model_type = model["id"], model["type"]
    result = {
        "model_id": model_id, "model_type": model_type,
        "model_version": MODEL_VERSIONS.get(model_type),
        "status": "not_assessed", "metrics": {},
        "assumptions": list(_ASSUMPTIONS.get(model_type, [])),
        "not_assessed": list(_NOT_ASSESSED.get(model_type, [])), "issues": [],
    }
    applicability = model_applicability(model_type)
    if applicability is not None:
        result["applicability"] = applicability
    from .chains import resolve
    project, bound_model, calculation_inputs, unavailable = resolve(project, model, prior_results)
    if calculation_inputs is not None:
        result["calculation_inputs"] = calculation_inputs
        result["assumptions"].extend("Explicit scalar assignment for " + role + ": " + link["rationale"]
                                     for role, link in sorted(model["links"].items()))
    if unavailable:
        result["issues"] = ["Upstream calculation evidence is unavailable for linked parameter " + role + "." for role in unavailable]
        result["not_assessed"].extend(result["issues"])
        return result
    if model_type not in _CALCULATORS and model_type not in {"orbital_trajectory", "power_energy_budget", "attitude_control", "powered_flight", "guided_ascent", "staged_ascent"}:
        result["not_assessed"] = [f"No maintained deterministic adapter supports model type {model_type}."]
        result["issues"] = ["Unsupported model type; no quantitative result was produced."]
    else:
        try:
            parameters = _bind_inputs(project, bound_model)
            if model_type == "staged_ascent":
                metrics, artifact = staged_ascent.evaluate(parameters)
                result["metrics"] = metrics
                result["staged_response"] = artifact
            elif model_type == "guided_ascent":
                metrics, artifact = guided_ascent.evaluate(parameters)
                result["metrics"] = metrics
                result["guided_response"] = artifact
            elif model_type == "powered_flight":
                metrics, artifact = powered_flight.evaluate(parameters)
                result["metrics"] = metrics
                result["flight_response"] = artifact
            elif model_type == "attitude_control":
                metrics, artifact = attitude.evaluate(parameters)
                result["metrics"] = metrics
                result["attitude_response"] = artifact
            elif model_type == "orbital_trajectory":
                metrics, artifact, accuracy = orbital_adapter.evaluate_with_accuracy(parameters, model.get("accuracy"))
                result["metrics"] = metrics
                result["simulation"] = artifact
                result["numerical_accuracy"] = accuracy
            elif model_type == "power_energy_budget":
                metrics, artifact = _power_budget(parameters)
                result["metrics"] = metrics
                result["power_budget"] = artifact
            else:
                metrics = _CALCULATORS[model_type](parameters)
                result["metrics"] = {
                    name: {"value": _finite(value, name), "unit": unit}
                    for name, (value, unit) in metrics.items()
                }
            result["status"] = "completed"
        except (ValueError, ArithmeticError) as exc:
            result["status"] = "invalid_inputs"
            result["metrics"] = {}
            result.pop("simulation", None)
            result.pop("power_budget", None)
            result.pop("attitude_response", None)
            result.pop("flight_response", None)
            result.pop("guided_response", None)
            result.pop("staged_response", None)
            result.pop("numerical_accuracy", None)
            result["issues"] = [str(exc)]
    return result


def evaluate_models(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Execute explicit scalar chains in dependency order without paid inference."""
    if not isinstance(project, dict) or not isinstance(project.get("inputs"), dict) or not isinstance(project.get("models"), list):
        raise ValueError("A project requires an inputs object and a models list.")
    for model in project["models"]:
        if (not isinstance(model, dict) or not isinstance(model.get("id"), str)
                or not model["id"].strip() or not isinstance(model.get("type"), str)
                or not model["type"].strip()):
            raise ValueError("Every model requires nonempty string id and type.")
    from .chains import ordered_models
    results = {}
    for model in ordered_models(project):
        results[model["id"]] = evaluate_model(project, model, results)
    return results
