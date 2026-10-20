"""Bounded, reproducible 3D point-mass orbit propagation in fixed SI units.

This module propagates declared initial conditions; it does not review a vehicle
or assign requirement verdicts. Velocity Verlet is second order, with no adaptive
steps or interpolation. Analytic elements only establish the input domain and
resolution limit; every returned state is a numerical integration sample.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any


SCENARIO_SCHEMA = "sixd.orbit-scenario.v1"
RESULT_SCHEMA = "sixd.orbit-simulation.v1"
FRAME = "body_centered_inertial_3d"
METHOD_VERSION = "1"
MAX_STEPS = 4096
MAX_ECCENTRICITY = 0.9
MAX_PERIODS = 8.0
MAX_PERICENTER_STEP = 0.02
MIN_DIMENSIONLESS_STEP = 1e-10
PERICENTER_CLEARANCE_FACTOR = 1.01
_LOADED_SOURCE_FINGERPRINT = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

_FIELDS = frozenset({
    "schema", "name", "mu_m3_s2", "exclusion_radius_m", "position_m",
    "velocity_m_s", "duration_s", "steps", "frame", "source",
})


def source_fingerprint() -> str:
    """SHA-256 captured from this solver's source when the module was loaded.

    A later disk edit cannot relabel a still-running older implementation.
    Restart/reload the application to use a changed implementation.
    """
    return _LOADED_SOURCE_FINGERPRINT


def default_spec() -> dict[str, Any]:
    """A synthetic inclined circular orbit, never inferred from project data."""
    mu = 3.986004418e14
    radius = 7_000_000.0
    speed = math.sqrt(mu / radius)
    inclination = math.radians(55.0)
    return {
        "schema": SCENARIO_SCHEMA,
        "name": "Synthetic inclined circular orbit",
        "mu_m3_s2": mu,
        "exclusion_radius_m": 6_371_000.0,
        "position_m": [radius, 0.0, 0.0],
        "velocity_m_s": [0.0, speed * math.cos(inclination), speed * math.sin(inclination)],
        "duration_s": 2.0 * math.pi * math.sqrt(radius ** 3 / mu),
        "steps": 1024,
        "frame": FRAME,
        "source": (
            "Constructed synthetic initial conditions with a declared Earth-like "
            "point-mass gravitational parameter and exclusion radius. No measured "
            "vehicle, flight, physical-test or CAD data."
        ),
    }


def _number(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite SI number, not text or a boolean.")
    # Comparing before conversion also safely rejects arbitrarily large integers.
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be between {minimum:g} and {maximum:g}.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite.")
    return 0.0 if number == 0.0 else number


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text of at most {limit} characters.")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError(f"{field} contains unsupported control characters.")
    return value.strip()


def _vector(value: Any, field: str, bound: float) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field} must be a JSON array of exactly three SI numbers.")
    return [_number(component, f"{field}[{index}]", -bound, bound)
            for index, component in enumerate(value)]


def _dot(left: list[float], right: list[float]) -> float:
    return math.fsum(a * b for a, b in zip(left, right))


def _cross(left: list[float], right: list[float]) -> list[float]:
    return [left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0]]


def _orbit(spec: dict[str, Any]) -> dict[str, Any]:
    radius = math.hypot(*spec["position_m"])
    speed_scale = math.sqrt(spec["mu_m3_s2"] / radius)
    time_scale = radius / speed_scale
    position = [component / radius for component in spec["position_m"]]
    velocity = [component / speed_scale for component in spec["velocity_m_s"]]
    energy = 0.5 * _dot(velocity, velocity) - 1.0
    if energy >= 0.0:
        raise ValueError("Only bounded elliptic two-body motion is supported; initial energy must be negative.")
    momentum = _cross(position, velocity)
    eccentricity_vector = [a - b for a, b in zip(_cross(velocity, momentum), position)]
    eccentricity = math.hypot(*eccentricity_vector)
    if eccentricity > MAX_ECCENTRICITY:
        raise ValueError(f"Eccentricity must be at most {MAX_ECCENTRICITY}; radial and near-parabolic motion are unsupported.")
    semi_major_axis = radius / (-2.0 * energy)
    pericenter = semi_major_axis * (1.0 - eccentricity)
    apocenter = semi_major_axis * (1.0 + eccentricity)
    period = 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / spec["mu_m3_s2"])
    pericenter_speed = math.sqrt(spec["mu_m3_s2"] / semi_major_axis
                                 * (1.0 + eccentricity) / (1.0 - eccentricity))
    if pericenter <= PERICENTER_CLEARANCE_FACTOR * spec["exclusion_radius_m"]:
        raise ValueError("Analytic pericenter must exceed 1.01 times the exclusion radius; collision/contact trajectories are unsupported.")
    period_limit = MAX_PERIODS * period
    # Element -> state -> reconstructed period introduces a few ulps even for
    # an exactly intended boundary case (independently reproduced with CSPICE).
    # This bounded roundoff allowance is not an engineering time tolerance.
    period_roundoff = 16 * math.ulp(period_limit)
    if spec["duration_s"] > period_limit and spec["duration_s"] - period_limit > period_roundoff:
        raise ValueError(f"duration_s may cover at most {MAX_PERIODS:g} analytic orbital periods.")
    dt = spec["duration_s"] / spec["steps"]
    if dt * pericenter_speed / pericenter > MAX_PERICENTER_STEP:
        raise ValueError("Time step is too coarse: duration_s / steps * pericenter_speed / pericenter_radius must be <= 0.02. Increase steps or shorten duration.")
    if dt / time_scale < MIN_DIMENSIONLESS_STEP:
        raise ValueError("Time step is too short relative to orbital scale for supported numerical resolution.")
    return {
        "radius_scale_m": radius,
        "speed_scale_m_s": speed_scale,
        "time_scale_s": time_scale,
        "position": position,
        "velocity": velocity,
        "semi_major_axis_m": semi_major_axis,
        "eccentricity": eccentricity,
        "pericenter_radius_m": pericenter,
        "apocenter_radius_m": apocenter,
        "orbital_period_s": period,
        "pericenter_step_ratio": dt * pericenter_speed / pericenter,
    }


def validate_spec(spec: Any) -> dict[str, Any]:
    """Validate declared physics, numerical resolution and bounded work.

    Return an independent canonical JSON-compatible object. Reject unknown
    fields so unsupported forces, units or frames cannot silently be ignored.
    """
    if not isinstance(spec, dict):
        raise ValueError("Scenario must be a JSON object.")
    if set(spec) != _FIELDS:
        raise ValueError("Scenario must contain exactly: " + ", ".join(sorted(_FIELDS)) + ".")
    if spec["schema"] != SCENARIO_SCHEMA:
        raise ValueError(f"schema must be {SCENARIO_SCHEMA}.")
    if spec["frame"] != FRAME:
        raise ValueError(f"frame must be {FRAME}, a nonrotating body-centered inertial frame.")
    if isinstance(spec["steps"], bool) or not isinstance(spec["steps"], int) or not 16 <= spec["steps"] <= MAX_STEPS:
        raise ValueError(f"steps must be an integer between 16 and {MAX_STEPS}.")
    canonical = {
        "schema": SCENARIO_SCHEMA,
        "name": _text(spec["name"], "name", 120),
        "mu_m3_s2": _number(spec["mu_m3_s2"], "mu_m3_s2", 1e-12, 1e25),
        "exclusion_radius_m": _number(spec["exclusion_radius_m"], "exclusion_radius_m", 1e-3, 1e13),
        "position_m": _vector(spec["position_m"], "position_m", 1e13),
        "velocity_m_s": _vector(spec["velocity_m_s"], "velocity_m_s", 1e8),
        "duration_s": _number(spec["duration_s"], "duration_s", 1e-6, 31_557_600.0),
        "steps": spec["steps"],
        "frame": FRAME,
        "source": _text(spec["source"], "source", 2000),
    }
    radius = math.hypot(*canonical["position_m"])
    if not 1.0 <= radius <= 1e13:
        raise ValueError("Initial position radius must be between 1 and 1e13 metres.")
    _orbit(canonical)
    return canonical


def _acceleration(position: list[float]) -> list[float]:
    radius = math.hypot(*position)
    return [-component / radius ** 3 for component in position]


def simulate(spec: Any) -> dict[str, Any]:
    """Propagate all three coordinates and return each actual discrete sample."""
    canonical = validate_spec(spec)
    orbit = _orbit(canonical)
    radius_scale = orbit["radius_scale_m"]
    speed_scale = orbit["speed_scale_m_s"]
    position = orbit["position"]
    velocity = orbit["velocity"]
    dt = canonical["duration_s"] / canonical["steps"]
    scaled_dt = dt / orbit["time_scale_s"]
    acceleration = _acceleration(position)
    initial_energy = 0.5 * _dot(velocity, velocity) - 1.0
    initial_momentum = _cross(position, velocity)
    momentum_norm = math.hypot(*initial_momentum)
    max_energy_error = 0.0
    max_momentum_error = 0.0
    samples = []

    for index in range(canonical["steps"] + 1):
        radius = math.hypot(*position)
        physical_radius = radius * radius_scale
        if not math.isfinite(physical_radius) or physical_radius <= canonical["exclusion_radius_m"]:
            raise ValueError("Propagation reached the exclusion radius or a nonfinite state; no completed result was produced.")
        energy = 0.5 * _dot(velocity, velocity) - 1.0 / radius
        momentum = _cross(position, velocity)
        max_energy_error = max(max_energy_error, abs(energy - initial_energy) / abs(initial_energy))
        max_momentum_error = max(max_momentum_error, math.hypot(
            *(component - initial for component, initial in zip(momentum, initial_momentum))) / momentum_norm)
        # Preserve the supplied initial state exactly; subsequent states are the
        # unrounded scaled numerical solution converted back to SI.
        physical_position = list(canonical["position_m"]) if index == 0 else [component * radius_scale for component in position]
        physical_velocity = list(canonical["velocity_m_s"]) if index == 0 else [component * speed_scale for component in velocity]
        sample = {
            "time_s": canonical["duration_s"] * index / canonical["steps"],
            "position_m": physical_position,
            "velocity_m_s": physical_velocity,
            "radius_m": math.hypot(*physical_position),
            "speed_m_s": math.hypot(*physical_velocity),
            "specific_energy_j_kg": 0.5 * _dot(physical_velocity, physical_velocity)
                                       - canonical["mu_m3_s2"] / math.hypot(*physical_position),
        }
        if not all(math.isfinite(value) for value in (
            sample["time_s"], *physical_position, *physical_velocity,
            sample["radius_m"], sample["speed_m_s"], sample["specific_energy_j_kg"],
        )):
            raise ValueError("Propagation produced a nonfinite state; no completed result was produced.")
        samples.append(sample)
        if index == canonical["steps"]:
            break
        next_position = [coordinate + component * scaled_dt + 0.5 * force * scaled_dt ** 2
                         for coordinate, component, force in zip(position, velocity, acceleration)]
        if math.hypot(*next_position) * radius_scale <= canonical["exclusion_radius_m"]:
            raise ValueError("Propagation reached the exclusion radius; no completed result was produced.")
        next_acceleration = _acceleration(next_position)
        velocity = [component + 0.5 * (force + next_force) * scaled_dt
                    for component, force, next_force in zip(velocity, acceleration, next_acceleration)]
        position, acceleration = next_position, next_acceleration

    return {
        "schema": RESULT_SCHEMA,
        "spec": canonical,
        "source_fingerprint": source_fingerprint(),
        "method": {
            "name": "velocity_verlet", "version": METHOD_VERSION, "order": 2,
            "time_step_s": dt, "steps": canonical["steps"],
            "force_model": "newtonian_point_mass_two_body",
            "coordinates": "Three-dimensional Cartesian, internally nondimensionalized",
            "sampling": "Every integration step; no interpolation or decimation",
        },
        "units": {"time": "s", "position": "m", "velocity": "m/s",
                  "specific_energy": "J/kg", "specific_angular_momentum": "m^2/s"},
        "samples": samples,
        "summary": {
            "sample_count": len(samples),
            "min_radius_m": min(sample["radius_m"] for sample in samples),
            "max_radius_m": max(sample["radius_m"] for sample in samples),
            "max_speed_m_s": max(sample["speed_m_s"] for sample in samples),
            "initial_specific_energy_j_kg": samples[0]["specific_energy_j_kg"],
            "final_specific_energy_j_kg": samples[-1]["specific_energy_j_kg"],
            "max_relative_energy_error": max_energy_error,
            "max_relative_angular_momentum_error": max_momentum_error,
            **{key: orbit[key] for key in ("semi_major_axis_m", "eccentricity",
               "pericenter_radius_m", "apocenter_radius_m", "orbital_period_s")},
        },
        "limits": {
            "max_steps": MAX_STEPS, "max_eccentricity": MAX_ECCENTRICITY,
            "max_orbital_periods": MAX_PERIODS,
            "max_pericenter_step_ratio": MAX_PERICENTER_STEP,
            "actual_pericenter_step_ratio": orbit["pericenter_step_ratio"],
            "pericenter_clearance_factor": PERICENTER_CLEARANCE_FACTOR,
        },
        "diagnostics_label": "Numerical diagnostics only; no engineering pass/fail finding.",
        "limitations": [
            "Conditional Newtonian point-mass, unforced elliptic two-body prediction in a nonrotating body-centered inertial frame.",
            "Initial conditions, gravitational parameter, exclusion radius and their source are supplied scenario data; their physical applicability is not verified.",
            "The exclusion radius is an input domain boundary, not a resolved body shape, atmosphere, terrain or contact model.",
            "No launch, landing, thrust, mass change, attitude, GNC, atmosphere, drag, heating, structural response, oblateness, third-body gravity or relativity.",
            "No measured physical-test or flight validation, uncertainty estimate, engineering requirement verdict or whole-vehicle assurance is produced.",
            "Velocity Verlet has finite second-order trajectory error; conservation diagnostics do not bound position or phase error.",
            "Stored samples are discrete numerical states; extrema between samples are not searched or certified.",
        ],
    }
