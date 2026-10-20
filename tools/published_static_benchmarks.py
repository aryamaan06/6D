"""External-equation benchmarks for the four algebraic engineering adapters.

Expected-value functions do not import sixd, its constants, or its calculators.
They use 60-digit Decimal arithmetic and independently transcribed source
equations. This is code verification against published mathematics, not hardware
validation or independent human certification. See PUBLISHED_STATIC_REFERENCES.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

NASA_ROCKET = "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/"
NASA_IMPULSE = "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/"
MIT_STRESS = "https://web.mit.edu/course/3/3.11/www/modules/bstress.pdf"
MIT_BEAM = "https://ocw.mit.edu/courses/3-052-nanomechanics-of-materials-and-biomaterials-spring-2007/d8d2ffa0503ad0adf0edb741ddb4e4c8_lec2_appendix.pdf"
NASA_RADIATOR = "https://ntrs.nasa.gov/api/citations/19720002481/downloads/19720002481.pdf"
NIST_CONSTANTS = "https://physics.nist.gov/cuu/Constants/Table/allascii.txt"
NASA_DRAG = "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/"
NASA_SMEATON = "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/smeaton-coefficient/"

# These are reference transcription contracts, deliberately not imported from
# the production parameter/unit registry under examination.
UNITS = {
    "ideal_propulsion": {"initial_mass": "kg", "dry_mass": "kg", "delta_v": "m/s", "specific_impulse": "s", "thrust": "N"},
    "static_cantilever": {"tip_force": "N", "length": "m", "young_modulus": "Pa", "second_moment": "m^4", "outer_fiber": "m"},
    "radiative_equilibrium": {"heat_input": "W", "area": "m^2", "emissivity": "1", "background_temperature": "K"},
    "drag_load": {"density": "kg/m^3", "relative_speed": "m/s", "drag_coefficient": "1", "reference_area": "m^2"},
}


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _quantity(value: Decimal | float | int, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


def propulsion_reference(values: dict[str, Any]) -> dict[str, Any]:
    """NASA mass ratio plus specific-impulse thrust relation; exact g0 from NIST."""
    with localcontext() as context:
        context.prec = 60
        mass, dry, dv, isp, thrust = map(_d, (values[k] for k in
            ("initial_mass", "dry_mass", "delta_v", "specific_impulse", "thrust")))
        velocity = Decimal("9.80665") * isp
        final = mass / (dv / velocity).exp()
        consumed = mass - final
        # Impulse balance supplies duration directly, independently of the
        # production implementation's computed mass-flow division.
        return {
            "propellant_required": _quantity(consumed, "kg"),
            "propellant_available": _quantity(mass - dry, "kg"),
            "propellant_margin": _quantity(final - dry, "kg"),
            "mass_flow": _quantity(thrust / velocity, "kg/s"),
            "burn_duration": _quantity(consumed * velocity / thrust, "s"),
        }


def cantilever_reference(values: dict[str, Any]) -> dict[str, Any]:
    """MIT stress Eq7 and tip-load compliance Eq11, magnitude convention."""
    with localcontext() as context:
        context.prec = 60
        force, length, modulus, moment, outer = map(_d, (values[k] for k in
            ("tip_force", "length", "young_modulus", "second_moment", "outer_fiber")))
        # Integrate the strain-energy density of M(x)=F(L-x): U=F²L³/(6EI).
        # Castigliano dU/dF gives the tip displacement, avoiding floating-point
        # operation order and constants from the production function.
        compliance = length ** 3 / (Decimal(3) * modulus * moment)
        return {"bending_stress": _quantity(force * length * outer / moment, "Pa"),
                "tip_deflection": _quantity(force * compliance, "m")}


def radiation_reference(values: dict[str, Any]) -> dict[str, Any]:
    """NASA CR1852 Eq3-2 with F=1; modern exact-SI CODATA sigma expression."""
    with localcontext() as context:
        context.prec = 60
        pi = Decimal("3.14159265358979323846264338327950288419716939937510582097494")
        # NIST exact h, k, c; sigma=2*pi^5*k^4/(15*h^3*c^2).
        sigma = (Decimal(2) * pi**5 * Decimal("1.380649e-23")**4 /
                 (Decimal(15) * Decimal("6.62607015e-34")**3 * Decimal("299792458")**2))
        q, area, emissivity, background = map(_d, (values[k] for k in
            ("heat_input", "area", "emissivity", "background_temperature")))
        fourth_power = q / (area * emissivity * sigma) + background**4
        return {"equilibrium_temperature": _quantity(fourth_power.sqrt().sqrt(), "K")}


def drag_reference(values: dict[str, Any]) -> dict[str, Any]:
    """NASA supplied-condition magnitude equation, evaluated as exact decimals."""
    with localcontext() as context:
        context.prec = 60
        density, speed, coefficient, area = map(_d, (values[k] for k in
            ("density", "relative_speed", "drag_coefficient", "reference_area")))
        pressure = density * speed * speed / Decimal(2)
        return {"dynamic_pressure": _quantity(pressure, "Pa"),
                "drag_force": _quantity(coefficient * area * pressure, "N")}


def _actual(model: str, values: dict[str, Any]) -> dict[str, Any]:
    # Production is used only on the actual-value side of this boundary.
    from sixd.engineering import evaluate_models
    project = {
        "inputs": {key: {"value": float(value), "unit": UNITS[model][key],
                         "source": "Published-reference benchmark; see source URLs"}
                   for key, value in values.items()},
        "models": [{"id": "benchmark", "type": model,
                    "inputs": {key: key for key in values}}],
    }
    return evaluate_models(project)["benchmark"]


def _case(identifier: str, model: str, values: dict[str, Any], expected: dict[str, Any],
          sources: list[str], limitations: list[str], *,
          kind: str = "published_equation_constructed_case", relative: float = 2e-12,
          absolute: float = 1e-12, per_metric: dict[str, dict[str, float]] | None = None,
          projection: str | None = None) -> dict[str, Any]:
    result = _actual(model, values)
    actual = dict(result["metrics"])
    if projection == "rocket_mass_fraction" and result["status"] == "completed":
        consumed = actual["propellant_required"]["value"]
        initial = float(values["initial_mass"])
        actual = {"propellant_fraction": _quantity(consumed / initial, "1"),
                  "mass_ratio": _quantity(initial / (initial - consumed), "1")}
    elif projection == "smeaton_coefficient" and result["status"] == "completed":
        # Convert measured force back to the published mixed-unit k. This is
        # merely a unit/projection boundary; no aerodynamic equation here.
        lbf = 0.45359237 * 9.80665
        actual = {"smeaton_coefficient": _quantity(actual["drag_force"]["value"] / lbf / 60**2, "lbf/(mph^2*ft^2)")}
    checks = {}
    for metric, reference in expected.items():
        observed = actual.get(metric)
        tolerance = (per_metric or {}).get(metric, {"absolute": absolute, "relative": relative})
        numeric = bool(observed and observed.get("unit") == reference["unit"] and
                       isinstance(observed.get("value"), (int, float)) and
                       math.isfinite(observed["value"]))
        error = abs(observed["value"] - reference["value"]) if numeric else None
        permitted = max(tolerance["absolute"], tolerance["relative"] * abs(reference["value"]))
        checks[metric] = {"absolute_error": error, "permitted_error": permitted,
                          "passed": numeric and error <= permitted}
    row = {"id": identifier, "model": model, "source_urls": sources,
            "reference_kind": kind,
            "inputs": {key: _quantity(value, UNITS[model][key]) for key, value in values.items()},
            "expected": expected, "actual": actual, "actual_status": result["status"],
            "tolerance": {"relative": relative, "absolute": absolute, "per_metric": per_metric or {}},
            "checks": checks, "passed": result["status"] == "completed" and all(c["passed"] for c in checks.values()),
            "limitations": limitations}
    if projection == "smeaton_coefficient" and "smeaton_coefficient" in actual:
        nominal_error = abs(actual["smeaton_coefficient"]["value"] - .00327)
        row["source_rounding_diagnostic"] = {
            "printed_nominal_inputs_result": actual["smeaton_coefficient"]["value"],
            "published_rounded_output": .00327,
            "output_only_half_last_digit": 5e-6,
            "output_only_check_passed": nominal_error <= 5e-6,
            "assumed_density_half_last_digit": .000005,
            "density_rounding_contribution": .5 * 1.28 * .000005 * 88**2 / 60**2,
            "interpretation": "Source nominal-input/output rounding discrepancy; not a production-calculator failure. Combined interval assumes the printed density was rounded, not a measured uncertainty estimate.",
        }
    return row


def _rejection(identifier: str, model: str, values: dict[str, Any], sources: list[str],
               reason: str) -> dict[str, Any]:
    result = _actual(model, values)
    expected = {"status": "invalid_inputs", "metrics_empty": True}
    actual = {"status": result["status"], "metrics_empty": result["metrics"] == {}}
    return {"id": identifier, "model": model, "source_urls": sources,
            "reference_kind": "domain_guard_not_physical_validation",
            "inputs": {key: _quantity(value, UNITS[model][key]) for key, value in values.items()},
            "expected": expected, "actual": actual, "tolerance": {"kind": "exact_status"},
            "passed": actual == expected, "limitations": [reason,
                "A rejected sign/range does not establish enforcement of every physical applicability assumption."]}


def run_checks() -> list[dict[str, Any]]:
    """Run offline, deterministic checks; no project DB or provider is accessed."""
    rows = []
    prop = {"initial_mass": 1200, "dry_mass": 400, "delta_v": 3000,
            "specific_impulse": 310, "thrust": 2300}
    p_sources = [NASA_ROCKET, NASA_IMPULSE, NIST_CONSTANTS]
    p_limits = ["Single ideal burn; no drag/gravity/steering losses, staging, reserves or real engine performance.",
                "High-precision independent arithmetic verifies the published equation, not flight applicability."]
    nasa_prop = {"initial_mass": 1000, "dry_mass": 100, "delta_v": 7620,
                 "specific_impulse": 350, "thrust": 1000}
    rows.append(_case("propulsion_nasa_rounded_worked_example", "ideal_propulsion", nasa_prop,
        {"propellant_fraction": _quantity(.9, "1"), "mass_ratio": _quantity(10, "1")},
        [NASA_ROCKET], ["NASA's approximate 25,000ft/s is converted using exact 0.3048m/ft. Mass and thrust are arbitrary normalization inputs.",
            "Published MR~10 and 90%propellant are rounded; tolerances are 10% on MR and 2percentage points on fraction. This is only a coarse sanity check."],
        kind="published_rounded_worked_example", per_metric={
            "propellant_fraction": {"absolute": .02, "relative": 0},
            "mass_ratio": {"absolute": 0, "relative": .1}}, projection="rocket_mass_fraction"))
    for name, values in [("general", prop), ("zero_delta_v", dict(prop, delta_v=0))]:
        rows.append(_case("propulsion_" + name, "ideal_propulsion", values,
            propulsion_reference(values), p_sources, p_limits, absolute=1e-10))
    rows.append(_rejection("propulsion_negative_delta_v", "ideal_propulsion", dict(prop, delta_v=-1),
        p_sources, "Adapter defines delta-v as a nonnegative prescribed magnitude."))

    beam = {"tip_force": 4, "length": .8, "young_modulus": 70e9,
            "second_moment": 3.2e-8, "outer_fiber": .004}
    beam_limits = ["Fixed-free, uniform, slender, linear-elastic Euler-Bernoulli beam with one transverse free-end point load.",
                   "No shear deformation, buckling, dynamics, joints or independently checked material allowable; constructed geometry/load."]
    rows.append(_case("cantilever_tip_load", "static_cantilever", beam,
        cantilever_reference(beam), [MIT_STRESS, MIT_BEAM], beam_limits))

    thermal = {"heat_input": 321, "area": 1.7, "emissivity": .84, "background_temperature": 210}
    thermal_limits = ["One isothermal grey surface, radiative equilibrium, unit view factor to a black isothermal enclosure, constant emissivity.",
        "No thermal transients, conduction/convection, gradients, solar/orbital load prediction or actual geometry validation.",
        "Decimal reference derives exact-SI sigma; production uses its ten-digit rounding. Relative T tolerance2e-10 includes that rounding."]
    rows.append(_case("radiation_finite_background", "radiative_equilibrium", thermal,
        radiation_reference(thermal), [NASA_RADIATOR, NIST_CONSTANTS], thermal_limits,
        relative=2e-10, absolute=1e-9))
    rows.append(_rejection("radiation_emissivity_above_one", "radiative_equilibrium", dict(thermal, emissivity=1.1),
        [NASA_RADIATOR], "Grey-surface infrared emissivity must be in(0,1]; zero area/emissivity is singular for positive heat."))

    drag = {"density": 1.17, "relative_speed": 17, "drag_coefficient": .83, "reference_area": .42}
    d_limits = ["Only a supplied-condition drag magnitude and dynamic pressure; coefficient must match area, attitude and flow regime.",
        "No coefficient prediction, compressibility correction, lift, moments, aeroheating or trajectory/load distribution."]
    with localcontext() as context:
        context.prec = 60
        foot = Decimal("0.3048")
        pound_force = Decimal("0.45359237") * Decimal("9.80665")
        # slug=lbf*s²/ft, so rhoSI=rhoSlugFt3*lbf/ft^4.
        nasa_drag = {"density": Decimal(".00237") * pound_force / foot**4,
                     "relative_speed": Decimal(88) * foot,
                     "drag_coefficient": Decimal("1.28"), "reference_area": foot**2}
    rows.append(_case("drag_nasa_smeaton_worked_example", "drag_load", nasa_drag,
        {"smeaton_coefficient": _quantity(.00327, "lbf/(mph^2*ft^2)")}, [NASA_SMEATON],
        ["NASA publishes k=.00327 for Cd1.28,rho.00237slug/ft3 and88ft/s=60mph; k is recovered after SI-only adapter execution.",
         "Printed inputs give k=.003262805333, outside output-only half-digit rounding. Density half-last-digit uncertainty contributes6.88e-6; adding output rounding5e-6 gives tolerance1.2e-5.",
         "This coarse low-speed flat-plate check does not validate rocket coefficients. Strict constructed-case Decimal agreement is checked separately."],
        kind="published_rounded_worked_example", relative=0, absolute=1.2e-5, projection="smeaton_coefficient"))
    rows.append(_case("drag_general", "drag_load", drag, drag_reference(drag), [NASA_DRAG], d_limits))
    rows.append(_rejection("drag_negative_speed_magnitude", "drag_load", dict(drag, relative_speed=-1),
        [NASA_DRAG], "The supplied relative speed is a magnitude, not a signed velocity component."))
    return rows


if __name__ == "__main__":
    checks = run_checks()
    print(json.dumps({"schema": "sixd.published-static-benchmarks.v1", "checks": checks,
                      "passed": all(row["passed"] for row in checks)}, indent=2, allow_nan=False))
    raise SystemExit(0 if all(row["passed"] for row in checks) else 1)
