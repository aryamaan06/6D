"""The deterministic verifier; language-model text cannot change its findings."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import math
import platform
import sys
from . import __version__
from .contracts import digest

NOT_TESTED = [
    "Whether the declared mathematical model represents any real mission or physical hardware.",
    "Eccentric orbits, burns, rendezvous, capture, landing or interplanetary transfers.",
    "Third bodies, nonspherical gravity, drag, radiation pressure and relativistic effects.",
    "Coordinate-frame transformations and inferred or converted input units.",
    "Arbitrary repositories, uploaded programs, external libraries or untrusted-code isolation.",
    "Payload, structural, thermal, electromagnetic, manufacturing or hardware qualification.",
    "Uncertainty in the central-body parameter or measured initial conditions.",
    "Long-duration, collision, singularity and fault-recovery behaviour.",
]


def specific_energy(state, mu):
    x, y, vx, vy = state
    return 0.5*(vx*vx+vy*vy) - mu/math.hypot(x, y)


def normalized_state_error(state, reference, contract):
    position = math.hypot(state[0]-reference[0], state[1]-reference[1])/contract.radius
    speed_scale = math.sqrt(contract.mu/contract.radius)
    velocity = math.hypot(state[2]-reference[2], state[3]-reference[3])/speed_scale
    return math.hypot(position, velocity)


def propagate(example, contract, steps, phase=None):
    c = contract if phase is None else contract.updated(phase_radians=phase)
    state = c.initial_state()
    duration = c.period * c.duration_orbits
    dt = duration/steps
    e0 = specific_energy(state, c.mu)
    max_drift = 0.0
    max_error = 0.0
    samples = []
    stride = max(1, steps//128)
    for index in range(steps+1):
        t = index*dt
        if not all(math.isfinite(value) for value in state):
            raise ArithmeticError("Non-finite propagated state.")
        energy_drift = (specific_energy(state, c.mu)-e0)/abs(e0)
        max_drift = max(max_drift, abs(energy_drift))
        max_error = max(max_error, normalized_state_error(state, c.analytic_state(t), c))
        if index % stride == 0 or index == steps:
            samples.append({"time_fraction": index/steps, "x_over_radius": state[0]/c.radius,
                            "y_over_radius": state[1]/c.radius, "energy_change_fraction": energy_drift})
        if index < steps:
            state = example.step(state, dt, c.mu, example.acceleration)
    return {"steps": steps, "dt_seconds": dt, "final_state": list(state),
            "final_state_error": normalized_state_error(state, c.analytic_state(duration), c),
            "max_state_error": max_error, "max_abs_energy_change_fraction": max_drift,
            "final_energy_change_fraction": (specific_energy(state,c.mu)-e0)/abs(e0),
            "samples": samples}


def force_experiment(example, contract):
    # Exact axes and independently specified diagonals expose coordinate-sign errors.
    # Radius and mu scaling are diagnostic probes, not changes to the locked contract.
    probes = []
    diagonal = math.sqrt(0.5)
    directions = ((1.0, 0.0), (diagonal, diagonal), (0.0, 1.0),
                  (-diagonal, diagonal), (-1.0, 0.0), (-diagonal, -diagonal),
                  (0.0, -1.0), (diagonal, -diagonal))
    for mu_factor in (0.5, 1.0, 2.0):
        probe_mu = mu_factor*contract.mu
        for factor in (0.7, 1.0, 1.4):
            r = factor*contract.radius
            magnitude = probe_mu/(r*r)
            for index, (unit_x, unit_y) in enumerate(directions):
                x, y = r*unit_x, r*unit_y
                expected = (-magnitude*unit_x, -magnitude*unit_y)
                observed = example.acceleration(x,y,probe_mu)
                if len(observed) != 2 or not all(math.isfinite(value) for value in observed):
                    raise ArithmeticError("The acceleration probe did not return two finite values.")
                residual = math.hypot(observed[0]-expected[0], observed[1]-expected[1])/magnitude
                probes.append({"radius_factor":factor, "mu_factor":mu_factor,
                               "probe_mu_m3_s2":probe_mu, "phase_radians":index*math.pi/4,
                               "position_m":[x,y], "expected_acceleration_m_s2":list(expected),
                               "observed_acceleration_m_s2":list(observed), "relative_residual":residual})
    worst = max(p["relative_residual"] for p in probes)
    return {"id":"central_force_reference", "status":"pass" if worst <= contract.force_relative_tolerance else "fail",
            "max_relative_residual":worst, "acceptance_threshold":contract.force_relative_tolerance,
            "threshold_basis":"Conservative floating-point comparison policy for the exposed analytic force; not physical uncertainty.",
            "comparison_assumptions":[
                "Autonomous attractive point-mass force, linear in mu and inverse-square in radius.",
                "Finite diagnostic samples cover four axes, four quadrants and three radius/mu scales; they do not establish the force at every state."],
            "probes":probes}


def refinement_experiment(example, contract):
    # Repeat in two rotated initial conditions; the reference is analytic, not another integrator.
    runs = [propagate(example,contract,n) for n in contract.refinement_steps]
    orders = []
    for coarse, fine in zip(runs,runs[1:]):
        e0, e1 = coarse["max_state_error"], fine["max_state_error"]
        orders.append(math.log(e0/e1,2) if e0>1e-14 and e1>1e-14 else None)
    phases = [contract.phase_radians+math.pi/3, contract.phase_radians+math.pi/2]
    repeat_orders = []
    for phase in phases:
        coarse = propagate(example,contract,contract.refinement_steps[-2],phase)
        fine = propagate(example,contract,contract.refinement_steps[-1],phase)
        repeat_orders.append(math.log(coarse["max_state_error"]/fine["max_state_error"],2)
                             if min(coarse["max_state_error"],fine["max_state_error"])>1e-14 else None)
    tail = [orders[-1], *repeat_orders]
    measurable = all(v is not None and math.isfinite(v) for v in tail)
    matches = measurable and all(abs(v-contract.declared_order)<=contract.order_tolerance for v in tail)
    reducing = all(f["max_state_error"]<c["max_state_error"] for c,f in zip(runs,runs[1:]))
    status = "pass" if matches and reducing else "fail" if measurable else "inconclusive"
    return {"id":"analytic_reference_refinement", "status":status,
            "declared_order":contract.declared_order, "observed_orders":orders,
            "rotated_initial_condition_orders":repeat_orders, "order_acceptance_half_width":contract.order_tolerance,
            "error_reduces_with_refinement":reducing,
            "threshold_basis":"Predeclared engineering tolerance for the finest-grid asymptotic estimate; no statistical confidence interval.",
            "error_definition":"Maximum dimensionless combined position/velocity error against the exact circular solution over one period.",
            "runs":runs}


def reversal_experiment(example, contract):
    """Check declared Verlet's self-adjoint property, not exact algorithm identity."""
    if contract.declared_method != "velocity_verlet":
        raise ValueError("Time-reversal comparison is supported only for declared velocity Verlet.")
    # This comparison policy is fixed before observing the candidate. The multiplier
    # allows conservative accumulated binary64 rounding in normalized, bounded states;
    # it is an engineering allowance, not a rigorous floating-point error bound.
    roundoff_multiplier = 128.0
    probes = []
    phases = (contract.phase_radians, contract.phase_radians+2*math.pi/3,
              contract.phase_radians+4*math.pi/3)
    for phase in phases:
        initial = contract.updated(phase_radians=phase).initial_state()
        for steps in (128, 256, 512):
            dt = contract.period/(4*steps)
            state = initial
            for step_size in (dt, -dt):
                for _ in range(steps):
                    state = example.step(state, step_size, contract.mu, example.acceleration)
                    if len(state) != 4 or not all(math.isfinite(value) for value in state):
                        raise ArithmeticError("The time-reversal experiment did not return four finite state values.")
            residual = normalized_state_error(state, initial, contract)
            threshold = roundoff_multiplier*sys.float_info.epsilon*(2*steps+1)
            probes.append({"initial_phase_radians":phase, "forward_steps":steps,
                           "reverse_steps":steps, "dt_seconds":dt,
                           "forward_duration_orbits":0.25,
                           "normalized_return_error":residual,
                           "acceptance_threshold":threshold,
                           "status":"pass" if residual <= threshold else "fail"})
    return {"id":"method_time_reversal",
            "status":"pass" if all(p["status"] == "pass" for p in probes) else "fail",
            "declared_method":contract.declared_method,
            "property":"Self-adjoint stepping: equal forward and negative-time steps return to the initial state.",
            "max_normalized_return_error":max(p["normalized_return_error"] for p in probes),
            "max_error_to_threshold_ratio":max(p["normalized_return_error"]/p["acceptance_threshold"] for p in probes),
            "roundoff_multiplier":roundoff_multiplier,
            "floating_point_epsilon":sys.float_info.epsilon,
            "threshold_basis":"Predeclared binary64 comparison allowance: 128 * epsilon * (forward_steps + reverse_steps + 1), in normalized state units; not a rigorous error bound.",
            "comparison_assumptions":[
                "Autonomous position-only central acceleration and a fixed step; no damping, events or irreversible state updates.",
                "Three circular initial phases, three step sizes and a quarter-period forward excursion with bounded, resolvable scales.",
                "Passing sampled reversibility and convergence does not prove exact algorithm identity or correctness at other states."],
            "probes":probes}


def audit(example, *, contract=None, review=None):
    c = contract or example.contract
    review = review or {"mode":"curated_demonstration", "human_acceptance_claimed":False}
    frozen_hash = c.sha256
    source = example.source_record()
    kernel_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    verification_sources = {name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ("kernel.py", "contracts.py", "__init__.py")}
    report = {"schema":"sixd.evidence-report.v1", "kernel_version":__version__,
        "created_at":datetime.now(timezone.utc).isoformat(), "example_id":example.id,
        "example_title":example.title, "execution_mode":"local_curated",
        "model_mode":"disabled", "live_model_calls":0,
        "contract":c.record(), "contract_sha256":frozen_hash,
        "contract_locked_before_experiments":True, "review":review,
        "candidate_source":source, "kernel_source_sha256":kernel_hash,
        "verification_sources":verification_sources,
        "runtime":{"python":sys.version.split()[0], "platform":platform.system()},
        "checks":[], "findings":[], "not_tested":list(NOT_TESTED),
        "claim_boundary":"Findings apply only to these curated functions, declared assumptions and supported checks. This is not correctness certification.",
        "evaluation_status":"Curated demonstrations; not a blinded benchmark or a measured customer result."}
    issues = c.ambiguities()
    if issues:
        report.update(verdict="inconclusive", evidence_strength="not_established",
                      summary="The contract is incomplete or outside the supported scope. No numerical experiments were run.")
        report["findings"] = [{"kind":"contract_ambiguity", "message":issue, "evidence_ids":[]} for issue in issues]
    else:
        try:
            force = force_experiment(example,c)
            report["checks"].append(force)
            refinement = refinement_experiment(example,c)
            report["checks"].append(refinement)
            reversal = None
            if c.declared_method == "velocity_verlet":
                reversal = reversal_experiment(example,c)
                report["checks"].append(reversal)
            if force["status"] == "fail":
                report.update(verdict="defect_likely", evidence_strength="repeated_supported_evidence",
                              summary="The exposed acceleration contradicts the declared attractive central-force model.")
                report["findings"].append({"kind":"force_model_mismatch", "message":report["summary"],
                                          "evidence_ids":[force["id"]], "source_function":source["acceleration_function"]})
            elif refinement["status"] == "inconclusive":
                report.update(verdict="inconclusive", evidence_strength="not_established",
                              summary="The convergence estimate could not be resolved above the comparison floor.")
            elif refinement["status"] == "fail":
                report.update(verdict="defect_likely", evidence_strength="repeated_supported_evidence",
                              summary="The measured convergence behaviour contradicts the declared numerical order.")
                report["findings"].append({"kind":"declared_order_mismatch", "message":report["summary"],
                                          "evidence_ids":[refinement["id"]],
                                          "source_functions":[source["step_function"],source["acceleration_function"]],
                                          "localization":"Not established: the integrated trajectory implicates the step/force combination; passing sampled force probes does not exclude unsampled force defects."})
            elif reversal is not None and reversal["status"] == "fail":
                report.update(verdict="defect_likely", evidence_strength="repeated_supported_evidence",
                              summary="The stepping behaviour violates the time-reversal property of declared velocity Verlet under the supported autonomous-force assumptions.")
                report["findings"].append({"kind":"declared_method_property_mismatch", "message":report["summary"],
                                          "evidence_ids":[reversal["id"]],
                                          "source_functions":[source["step_function"],source["acceleration_function"]],
                                          "localization":"A sampled method property fails; this does not establish exact algorithm identity or uniquely localize the cause."})
            elif c.declared_method == "explicit_euler":
                report.update(verdict="method_limitation", evidence_strength="repeated_supported_evidence",
                              summary="The observed first-order convergence matches explicit Euler. Its energy drift is a method limitation in this case, not evidence of a force defect.")
                report["findings"].append({"kind":"nonconservative_method", "message":report["summary"],
                                          "evidence_ids":[force["id"],refinement["id"]]})
            else:
                report.update(verdict="no_defect_found_in_scope", evidence_strength="repeated_supported_evidence",
                              summary="The sampled force reference, second-order refinement and time-reversal checks found no supported defect in this example; exact method identity is not established.")
        except (ArithmeticError, ValueError, OverflowError, ZeroDivisionError) as exc:
            report.update(verdict="inconclusive", evidence_strength="not_established",
                          summary="An experiment could not complete reliably. No physical diagnosis is inferred from this failure.")
            report["findings"].append({"kind":"experiment_execution_failure", "message":str(exc), "evidence_ids":[]})
    if c.sha256 != frozen_hash:
        raise RuntimeError("The contract changed during the audit.")
    report["audit_id"] = digest({"contract":frozen_hash, "candidate":source["source_sha256"],
                               "verification_sources":verification_sources, "checks":report["checks"], "verdict":report["verdict"]})[:20]
    report["report_payload_sha256"] = digest(report)
    return report
