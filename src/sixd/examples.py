"""Human-written curated auditees. This is not an arbitrary-code sandbox."""
from dataclasses import dataclass
from hashlib import sha256
import inspect
import math
from typing import Callable
from .contracts import Contract


def attractive_acceleration(x, y, mu):
    inverse_r3 = 1.0 / math.hypot(x, y)**3
    return -mu*x*inverse_r3, -mu*y*inverse_r3


def outward_acceleration(x, y, mu):
    # Seeded defect: the sign makes the central force repulsive.
    inverse_r3 = 1.0 / math.hypot(x, y)**3
    return mu*x*inverse_r3, mu*y*inverse_r3


def verlet_step(state, dt, mu, acceleration):
    x, y, vx, vy = state
    ax, ay = acceleration(x, y, mu)
    xn = x + vx*dt + 0.5*ax*dt*dt
    yn = y + vy*dt + 0.5*ay*dt*dt
    anx, any_ = acceleration(xn, yn, mu)
    return xn, yn, vx + 0.5*(ax+anx)*dt, vy + 0.5*(ay+any_)*dt


def euler_step(state, dt, mu, acceleration):
    x, y, vx, vy = state
    ax, ay = acceleration(x, y, mu)
    return x+vx*dt, y+vy*dt, vx+ax*dt, vy+ay*dt


@dataclass(frozen=True)
class Example:
    id: str
    title: str
    summary: str
    step: Callable
    acceleration: Callable
    contract: Contract

    def source_record(self):
        step_source = inspect.getsource(self.step)
        force_source = inspect.getsource(self.acceleration)
        return {"step_function": self.step.__name__, "acceleration_function": self.acceleration.__name__,
                "step_source": step_source, "acceleration_source": force_source,
                "source_sha256": sha256((step_source + "\n" + force_source).encode()).hexdigest()}

    def public_record(self):
        return {"id": self.id, "title": self.title, "summary": self.summary,
                "contract": self.contract.record(), "contract_sha256": self.contract.sha256,
                "source": self.source_record()}


BASE = Contract()
EXAMPLES = {
    "verlet_correct": Example("verlet_correct", "Circular orbit with velocity Verlet",
        "Curated reference implementation. Check it against an exact circular orbit.",
        verlet_step, attractive_acceleration, BASE),
    "force_sign_error": Example("force_sign_error", "A changed gravity implementation",
        "Curated implementation with a deliberately seeded force defect.",
        verlet_step, outward_acceleration, BASE.updated(revision="2")),
    "euler_method_limit": Example("euler_method_limit", "Circular orbit with explicit Euler",
        "A correctly declared first-order method. Its numerical drift needs context.",
        euler_step, attractive_acceleration,
        BASE.updated(declared_method="explicit_euler", declared_order=1)),
    "wrong_order": Example("wrong_order", "A changed stepping implementation",
        "Curated implementation that no longer matches its declared second-order contract.",
        euler_step, attractive_acceleration, BASE.updated(revision="2")),
    "ambiguous_frame": Example("ambiguous_frame", "A contract missing its reference frame",
        "The source is available, but the intended coordinate frame is unspecified.",
        verlet_step, attractive_acceleration, BASE.updated(frame="unspecified")),
}


def get_example(identifier):
    try:
        return EXAMPLES[identifier]
    except KeyError:
        raise ValueError("Choose one of the registered curated examples.") from None
