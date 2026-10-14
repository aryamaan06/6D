"""Reviewed, hash-addressed assumptions for the one supported model family."""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import math

SCHEMA = "sixd.circular-orbit-contract.v1"
FRAME = "body_centered_inertial_2d"


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Contract:
    schema: str = SCHEMA
    revision: str = "1"
    family: str = "point_mass_two_body_circular_orbit"
    description: str = "Synthetic circular-orbit reference case, not a flight mission."
    mu: float = 3.986004418e14
    radius: float = 7.0e6
    phase_radians: float = 0.0
    position_unit: str = "m"
    velocity_unit: str = "m/s"
    mu_unit: str = "m^3/s^2"
    frame: str = FRAME
    declared_method: str = "velocity_verlet"
    declared_order: int = 2
    duration_orbits: float = 1.0
    refinement_steps: tuple = (512, 1024, 2048, 4096)
    force_relative_tolerance: float = 1e-10
    order_tolerance: float = 0.20

    def record(self) -> dict:
        return asdict(self)

    @property
    def sha256(self) -> str:
        return digest(self.record())

    def updated(self, **changes):
        return replace(self, **changes)

    def ambiguities(self) -> list[str]:
        issues = []
        if self.schema != SCHEMA or self.family != "point_mass_two_body_circular_orbit":
            issues.append("The model family or contract schema is outside supported coverage.")
        if (self.position_unit, self.velocity_unit, self.mu_unit) != ("m", "m/s", "m^3/s^2"):
            issues.append("The contract must explicitly use m, m/s and m^3/s^2. Unit conversion is not inferred.")
        if self.frame != FRAME:
            issues.append("An explicit body-centred inertial 2D frame is required. Frame transformations are not supported.")
        for label, value in (("mu", self.mu), ("radius", self.radius)):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                issues.append(f"{label} must be a finite positive number.")
        if not isinstance(self.phase_radians, (int, float)) or not math.isfinite(self.phase_radians):
            issues.append("The initial phase must be finite.")
        supported_methods = {"velocity_verlet": 2, "explicit_euler": 1}
        if supported_methods.get(self.declared_method) != self.declared_order:
            issues.append("The declared method/order pair is not supported or is inconsistent.")
        if self.duration_orbits != 1.0:
            issues.append("This version checks exactly one circular-orbit period.")
        if tuple(self.refinement_steps) != (512, 1024, 2048, 4096):
            issues.append("This version uses the predeclared four-level refinement experiment.")
        if self.force_relative_tolerance != 1e-10 or self.order_tolerance != 0.20:
            issues.append("Acceptance thresholds are fixed in this version; changing them requires a new verification policy.")
        if not issues:
            try:
                rate = self.angular_rate
                if not math.isfinite(rate) or rate <= 0 or not math.isfinite(self.period):
                    issues.append("The chosen scales cannot be resolved by this numeric implementation.")
            except (OverflowError, ZeroDivisionError, ValueError):
                issues.append("The chosen scales cannot be resolved by this numeric implementation.")
        return issues

    @property
    def angular_rate(self) -> float:
        return math.sqrt(self.mu / self.radius**3)

    @property
    def period(self) -> float:
        return 2 * math.pi / self.angular_rate

    def initial_state(self) -> tuple:
        c, s = math.cos(self.phase_radians), math.sin(self.phase_radians)
        speed = math.sqrt(self.mu / self.radius)
        return (self.radius*c, self.radius*s, -speed*s, speed*c)

    def analytic_state(self, elapsed: float) -> tuple:
        phase = self.phase_radians + self.angular_rate * elapsed
        speed = math.sqrt(self.mu / self.radius)
        return (self.radius*math.cos(phase), self.radius*math.sin(phase),
                -speed*math.sin(phase), speed*math.cos(phase))
