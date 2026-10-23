"""Constructed component-screening examples, not a real spacecraft design."""
from copy import deepcopy

from .simulation import default_spec


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
    return {"baseline": baseline, "revised": revised, "missing_evidence": missing,
            "orbital_review": _orbital_review(baseline), "power_budget": _power_review(baseline),
            "attitude_review": _attitude_review(baseline), "chain_review": _chain_review(baseline),
            "powered_flight_review": powered_flight_review()}


def powered_flight_review():
    """Synthetic vertical-flight case; all numbers are illustrative inputs."""
    from .powered_flight import PARAMETERS
    values = dict(initial_mass=1000, dry_mass=700, thrust=20000, specific_impulse=250,
                  reference_area=.8, drag_coefficient=.4, reference_density=1.225,
                  scale_height=8500, gravitational_parameter=3.986004418e14,
                  launch_radius=6371000, coast_duration=20, steps=128,
                  altitude_numerical_tolerance=.5, velocity_numerical_tolerance=.02,
                  relative_numerical_tolerance=1e-6)
    inputs = {key: _input(value, PARAMETERS[key]) for key,value in values.items()}
    inputs.update(minimum_burnout_altitude=_input(5000, 'm'),
                  maximum_dynamic_pressure=_input(50000, 'Pa'),
                  maximum_upward_acceleration=_input(25, 'm/s^2'))
    requirements = []
    for identity,title,metric,operator,limit in (
        ('burnout_height', 'Declared minimum burnout altitude', 'burnout_altitude', '>=', 'minimum_burnout_altitude'),
        ('dynamic_pressure', 'Declared maximum sampled dynamic pressure', 'max_sampled_dynamic_pressure', '<=', 'maximum_dynamic_pressure'),
        ('upward_acceleration', 'Declared maximum sampled upward acceleration', 'max_sampled_upward_acceleration', '<=', 'maximum_upward_acceleration'),
    ):
        requirements.append(dict(id=identity,title=title,model_id='vertical_flight',metric=metric,
                                 operator=operator,limit_input=limit,critical=True))
    return dict(schema='sixd.project.v1', project_id='constructed-powered-flight', revision='1',
                name='Constructed powered vertical flight', lifecycle_stage='simulation',
                description='Synthetic vertical ascent through burnout and above-surface coast. Constant engine and drag inputs in an exponential atmosphere; no staging, steering, aeroheating or landing. Inputs and criteria are illustrative, not flight data.',
                inputs=inputs, models=[dict(id='vertical_flight', type='powered_flight', inputs={key:key for key in PARAMETERS})],
                requirements=requirements)


def _chain_review(baseline):
    """An explicitly declared scalar drag-to-beam mapping, not a flight case."""
    project = deepcopy(baseline)
    project.update(project_id="constructed-calculation-chain", name="Constructed aerodynamic load and structure review",
        description="Synthetic scalar drag-to-beam reference. The full drag magnitude is declared as a transverse free-end point load on a static beam. Geometry, direction and load case are assumptions; the independent thermal case is not coupled. No vehicle or mission validation is implied.")
    project["inputs"].update(density=_input(.4,"kg/m^3"), relative_speed=_input(10,"m/s"),
        drag_coefficient=_input(.5,"1"), reference_area=_input(2,"m^2"), mount_length=_input(2,"m"),
        young_modulus=_input(2e11,"Pa"), second_moment=_input(1e-6,"m^4"), maximum_drag_force=_input(10,"N"))
    by_id = {model["id"]: model for model in project["models"]}
    beam, aero, thermal = by_id["mount"], by_id["atmospheric_load"], by_id["thermal"]
    beam["id"] = "beam"
    beam["description"] = "Ideal static cantilever with an explicitly mapped aerodynamic point load."
    del beam["inputs"]["tip_force"]
    aero["id"] = "aero"
    aero["description"] = "Supplied steady density, relative speed, coefficient and reference area."
    beam["links"] = {"tip_force": {"model_id":"aero", "metric":"drag_force", "unit":"N",
        "rationale":"For this constructed load case, apply the entire drag-force magnitude as a transverse point load at the beam free end. Load direction, location and boundary conditions are explicitly assumed."}}
    # Deliberately reverse dependency order to exercise topological execution.
    project["models"] = [beam, aero, thermal]
    project["requirements"] = [r for r in project["requirements"] if r["model_id"] != "propulsion"]
    for requirement in project["requirements"]:
        requirement["model_id"] = {"mount":"beam", "atmospheric_load":"aero"}.get(requirement["model_id"], requirement["model_id"])
    used = {key for model in project["models"] for key in model["inputs"].values()} | {r["limit_input"] for r in project["requirements"]}
    project["inputs"] = {key:value for key,value in project["inputs"].items() if key in used}
    return project


def _attitude_review(baseline):
    """Constructed critically damped single-axis response; not flight data."""
    from .attitude import PARAMETERS
    import math
    values = dict(inertia=10, initial_angle=0, initial_rate=0, target_angle=0.2,
                  proportional_gain=1, derivative_gain=2*math.sqrt(10), max_torque=1,
                  disturbance_torque=0, duration=40, steps=512, assessment_start=30,
                  angle_numerical_tolerance=1e-6, rate_numerical_tolerance=1e-6)
    inputs = {key:_input(value, PARAMETERS[key]) for key,value in values.items()}
    inputs.update(pointing_limit=_input(0.001,'rad'), rate_limit=_input(0.001,'rad/s'))
    for key in ('heat_input','radiator_area','emissivity','background_temperature','maximum_temperature'):
        inputs[key] = deepcopy(baseline['inputs'][key])
    return {
        'schema':'sixd.project.v1', 'project_id':'constructed-attitude-review',
        'name':'Constructed single-axis pointing review', 'revision':'1', 'lifecycle_stage':'simulation',
        'description':'Illustrative rigid principal-axis PD control with a fixed target and ideal torque source. Values and limits are constructed references, not real spacecraft data. The separate thermal calculation is not coupled to control.',
        'inputs':inputs,
        'models':[{'id':'pointing', 'type':'attitude_control',
                   'description':'Critically damped unsaturated reference; ideal state feedback, no navigation or wheel momentum model.',
                   'inputs':{key:key for key in PARAMETERS}},
                  deepcopy(next(m for m in baseline['models'] if m['id']=='thermal'))],
        'requirements':[
            {'id':'pointing_window', 'title':'Sampled pointing error during declared assessment window',
             'model_id':'pointing', 'metric':'max_assessed_error', 'operator':'<=','limit_input':'pointing_limit','critical':True},
            {'id':'rate_window', 'title':'Sampled angular rate during declared assessment window',
             'model_id':'pointing', 'metric':'max_assessed_rate','operator':'<=','limit_input':'rate_limit','critical':True},
            deepcopy(next(r for r in baseline['requirements'] if r['id']=='thermal_limit'))],
    }


def _power_review(baseline):
    """Constructed concurrent loads and independent thermal reference."""
    scalars = {
        "usable_battery_energy": (6000, "J"), "battery_power_limit": (60, "W"), "bus_power_limit": (100, "W"),
        "cruise_duration": (100, "s"), "cruise_generation": (20, "W"), "avionics_power": (10, "W"),
        "avionics_count": (1, "1"), "payload_power": (30, "W"), "payload_count": (2, "1"),
        "downlink_duration": (50, "s"), "downlink_generation": (100, "W"), "radio_power": (40, "W"),
        "radio_count": (1, "1"), "minimum_power_margin": (0, "W"), "minimum_energy_margin": (0, "J"),
        "declared_load_allowance": (80, "W"),
    }
    inputs = {key: _input(value, unit) for key, (value, unit) in scalars.items()}
    for key in ("heat_input", "radiator_area", "emissivity", "background_temperature", "maximum_temperature"):
        inputs[key] = deepcopy(baseline["inputs"][key])
    bindings = {"usable_battery_energy": "usable_battery_energy", "max_battery_power": "battery_power_limit", "bus_power_limit": "bus_power_limit"}
    for index, name in ((1, "cruise"), (2, "downlink")):
        prefix = f"mode.{index}.{name}."
        bindings[prefix + "duration"] = name + "_duration"
        bindings[prefix + "generation"] = name + "_generation"
        for load in (("avionics", "payload") if name == "cruise" else ("avionics", "radio")):
            bindings[prefix + "load." + load + ".power"] = load + "_power"
            bindings[prefix + "load." + load + ".count"] = load + "_count"
    return {
        "schema": "sixd.project.v1", "project_id": "constructed-power-energy-review", "name": "Constructed operating-mode power and energy review",
        "revision": "1", "lifecycle_stage": "design",
        "description": "Synthetic constant simultaneous loads in two sequential modes, declared generation and upfront reserve-adjusted usable bus battery energy. No charging, illumination or state-of-charge model. The thermal example is independent; values are illustrative, not real spacecraft data.",
        "inputs": inputs,
        "models": [{"id": "electrical_budget", "type": "power_energy_budget", "description": "Explicit mode durations and equipment concurrency. Generation surplus has no recharge credit.", "inputs": bindings}, deepcopy(next(m for m in baseline["models"] if m["id"] == "thermal"))],
        "requirements": [
            {"id": "power_capacity", "title": "Power capacity covers every declared mode", "model_id": "electrical_budget", "metric": "minimum_power_margin", "operator": ">=", "limit_input": "minimum_power_margin", "critical": True},
            {"id": "usable_energy", "title": "Usable battery energy covers the declared schedule", "model_id": "electrical_budget", "metric": "battery_energy_margin", "operator": ">=", "limit_input": "minimum_energy_margin", "critical": True},
            deepcopy(next(r for r in baseline["requirements"] if r["id"] == "thermal_limit")),
        ],
        "systems": [
            {"id": "space_system", "title": "Constructed space system", "description": "Organization only; not a complete vehicle.", "parent_id": None, "model_ids": []},
            {"id": "electrical", "title": "Electrical power", "description": "Bounded bus power and energy budget.", "parent_id": "space_system", "model_ids": ["electrical_budget"]},
            {"id": "load_allocation", "title": "Declared load allowance", "description": "Declared allocation only; no downstream solver consumes the interface.", "parent_id": "space_system", "model_ids": []},
            {"id": "radiator", "title": "Independent thermal case", "description": "Explicit static heat input; electrical output is not automatically converted to heat.", "parent_id": "space_system", "model_ids": ["thermal"]},
        ],
        "interfaces": [{"id": "declared_bus_allowance", "title": "Peak simultaneous load against declared allocation", "description": "Scalar comparison only; not a data feed into another model.", "from_system": "electrical", "to_system": "load_allocation", "source": {"kind": "model_metric", "model_id": "electrical_budget", "metric": "peak_load_power"}, "target_input": "declared_load_allowance", "quantity": "Bus load power", "unit": "W", "operator": "<=", "critical": True}],
    }


def _orbital_review(baseline):
    """Constructed orbit criteria and an explicitly independent thermal case."""
    spec = default_spec()
    # Three guarded grids (512, 1024, 2048) can demonstrate refinement here.
    # These are labelled illustrative criteria, never mission requirements.
    spec["steps"] = 2048
    scalars = {
        "mu_m3_s2": (spec["mu_m3_s2"], "m^3/s^2"),
        "exclusion_radius_m": (spec["exclusion_radius_m"], "m"),
        "duration_s": (spec["duration_s"], "s"), "steps": (spec["steps"], "1"),
        **{f"position_{axis}": (spec["position_m"][index], "m") for index, axis in enumerate("xyz")},
        **{f"velocity_{axis}": (spec["velocity_m_s"][index], "m/s") for index, axis in enumerate("xyz")},
    }
    inputs = {key: _input(value, unit) for key, (value, unit) in scalars.items()}
    inputs.update({
        "minimum_sampled_radius": _input(6_900_000, "m"),
        "maximum_sampled_radius": _input(7_100_000, "m"),
        "maximum_sampled_speed": _input(7_800, "m/s"),
        "maximum_final_radius": _input(7_050_000, "m"),
    })
    for key in ("heat_input", "radiator_area", "emissivity", "background_temperature", "maximum_temperature"):
        inputs[key] = deepcopy(baseline["inputs"][key])
    models = [{"id": "orbit", "type": "orbital_trajectory",
               "description": "Constructed inclined circular orbit; sampled criteria apply only to the declared duration and integration grid.",
               "accuracy": {"position_tolerance_m": 500, "velocity_tolerance_m_s": 0.6,
                            "source": "Constructed demonstration grid-agreement allowances only; not measured or mission accuracy requirements."},
               "inputs": {key: key for key in scalars}},
              deepcopy(next(model for model in baseline["models"] if model["id"] == "thermal"))]
    models[1]["description"] = "Independent static thermal case with explicitly supplied heat input; no orbital/thermal coupling is inferred."
    requirements = []
    for identity, title, metric, operator, limit in (
        ("orbit_min_radius", "Minimum sampled radius over the declared window", "min_radius_m", ">=", "minimum_sampled_radius"),
        ("orbit_max_radius", "Maximum sampled radius over the declared window", "max_radius_m", "<=", "maximum_sampled_radius"),
        ("orbit_max_speed", "Maximum sampled speed over the declared window", "max_speed_m_s", "<=", "maximum_sampled_speed"),
        ("orbit_final_radius", "Final-sample radius at the declared duration", "final_radius_m", "<=", "maximum_final_radius"),
    ):
        requirements.append({"id": identity, "title": title, "model_id": "orbit", "metric": metric,
                             "operator": operator, "limit_input": limit, "critical": True})
    requirements.append(deepcopy(next(item for item in baseline["requirements"] if item["id"] == "thermal_limit")))
    return {
        "schema": "sixd.project.v1", "project_id": "constructed-orbital-review",
        "name": "Constructed orbital engineering review", "revision": "1", "lifecycle_stage": "simulation",
        "description": "Synthetic bounded two-body orbit with explicit sampled criteria and an independent thermal model. Values and limits are illustrative; no real spacecraft, flight validation or complete mission is represented.",
        "inputs": inputs, "models": models, "requirements": requirements,
    }
