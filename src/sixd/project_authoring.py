"""Read-only authoring guidance for explicit v1 project records.

Catalog and preflight describe maintained contracts without running calculators,
inventing numerical defaults or predicting requirement findings. Parameter
domains and model applicability remain the maintained adapters' responsibility.
"""
from copy import deepcopy

from . import lifecycle
from . import attitude, powered_flight
from .engineering import MODEL_PARAMETERS, MODEL_VERSIONS, _ASSUMPTIONS, _NOT_ASSESSED, model_applicability


_MODEL_DETAILS = {
    "powered_flight": (
        "Powered vertical flight",
        "Constant-thrust vertical ascent through burnout and above-surface coast, with gravity, exponential-atmosphere drag and analytical mass depletion. Sampled checks with declared grid tolerances.",
        list(powered_flight.METRICS),
    ),
    "attitude_control": (
        "Single-axis spacecraft pointing",
        "Continuous PD control of a rigid principal axis with a fixed target, ideal clipped torque and constant supplied disturbance. Saved sampled checks only.",
        list(attitude.METRICS),
    ),
    "power_energy_budget": (
        "Operating-mode power and energy budget",
        "Constant simultaneous equipment loads in named sequential modes; supplied bus generation and usable battery energy, with no recharge credit.",
        [("peak_load_power", "W", "Peak simultaneous load"),
         ("minimum_power_margin", "W", "Minimum power-capacity margin"),
         ("total_load_energy", "J", "Total load energy"),
         ("total_generated_energy", "J", "Total supplied generation energy"),
         ("battery_energy_required", "J", "Required usable battery energy"),
         ("battery_energy_margin", "J", "Usable battery energy margin"),
         ("minimum_generation_margin", "W", "Minimum generation minus load"),
         ("max_battery_power_required", "W", "Maximum battery power required"),
         ("minimum_bus_power_margin", "W", "Minimum bus capacity margin"),
         ("minimum_battery_power_margin", "W", "Minimum battery power-capacity margin"),
         ("total_duration", "s", "Total declared mode duration"),
         ("surplus_generation_energy", "J", "Generation surplus without recharge credit")],
    ),
    "ideal_propulsion": (
        "Ideal propulsion budget",
        "Single ideal burn using supplied mass, delta-v, specific impulse and constant thrust.",
        [("propellant_required", "kg", "Required propellant"),
         ("propellant_available", "kg", "Available propellant"),
         ("propellant_margin", "kg", "Propellant margin"),
         ("mass_flow", "kg/s", "Mass flow"),
         ("burn_duration", "s", "Required burn duration")],
    ),
    "static_cantilever": (
        "Static cantilever beam",
        "Small-deflection Euler-Bernoulli beam with a rigid clamp and transverse tip load.",
        [("bending_stress", "Pa", "Maximum bending stress"),
         ("tip_deflection", "m", "Tip deflection")],
    ),
    "radiative_equilibrium": (
        "Steady radiative equilibrium",
        "One isothermal grey surface radiating to an isothermal black background.",
        [("equilibrium_temperature", "K", "Equilibrium temperature")],
    ),
    "drag_load": (
        "Single-condition drag load",
        "Dynamic pressure and drag magnitude from an explicitly supplied atmospheric condition.",
        [("dynamic_pressure", "Pa", "Dynamic pressure"),
         ("drag_force", "N", "Drag force")],
    ),
    "orbital_trajectory": (
        "Sampled two-body orbital trajectory",
        "Unforced three-dimensional elliptic two-body translation over the supplied duration and grid.",
        [("min_radius_m", "m", "Minimum sampled radius"),
         ("max_radius_m", "m", "Maximum sampled radius"),
         ("max_speed_m_s", "m/s", "Maximum sampled speed"),
         ("final_radius_m", "m", "Final-sample radius"),
         ("final_speed_m_s", "m/s", "Final-sample speed")],
    ),
}


def catalog():
    """Return exact maintained binding contracts and documented scalar metrics."""
    models = []
    for model_type, parameters in MODEL_PARAMETERS.items():
        title, description, metrics = _MODEL_DETAILS[model_type]
        models.append({
            "type": model_type, "title": title, "description": description,
            "version": MODEL_VERSIONS[model_type],
            "parameters": [{"name": name, "unit": unit} for name, unit in parameters.items()],
            "metrics": [{"name": name, "unit": unit, "label": label} for name, unit, label in metrics],
            "assumptions": deepcopy(_ASSUMPTIONS[model_type]),
            "not_assessed": deepcopy(_NOT_ASSESSED[model_type]),
            "applicability": model_applicability(model_type),
        })
        if model_type == "power_energy_budget":
            models[-1]["profile"] = {"schema": "sixd.power-mode-bindings.v1", "editor": "power_energy",
                "mode_limit": 16, "total_load_limit": 128,
                "description": "Use Power & energy to bind named modes, positive durations, available generation and simultaneous equipment power/count records. All numeric values come from explicit project inputs.",
                "roles": {"mode.<index>.<mode_id>.duration": "s", "mode.<index>.<mode_id>.generation": "W",
                          "mode.<index>.<mode_id>.load.<load_id>.power": "W", "mode.<index>.<mode_id>.load.<load_id>.count": "1"}}
    return {"schema": "sixd.model-catalog.v1", "models": models,
            "operators": ["<=", ">=", "=="],
            "lifecycle_stages": ["design", "simulation", "physical_test", "operation"]}


def preflight(project):
    """Describe authoring errors/warnings without calculating any evidence.

    Structurally invalid project data produces issues rather than an exception.
    A ready configuration can still be rejected by an adapter's numerical-domain
    checks; readiness is not a prediction of successful or passing calculations.
    """
    issues = []

    def issue(severity, code, path, message):
        issues.append({"severity": severity, "code": code, "path": path, "message": message})

    counts = {key: len(project[key]) if isinstance(project, dict)
              and isinstance(project.get(key), dict if key == "inputs" else list) else 0
              for key in ("inputs", "models", "requirements")}

    def result():
        return {"schema": "sixd.authoring-preflight.v1",
                "can_run": not any(item["severity"] == "error" for item in issues),
                "issues": issues, "counts": counts}

    try:
        snapshot = lifecycle.validate_project(project, allow_empty=True)
    except (ValueError, TypeError, OverflowError) as exc:
        issue("error", "invalid_project", "project", str(exc))
        return result()

    if not snapshot["models"]:
        issue("error", "empty_models", "project.models", "Add at least one model before running checks.")
    if not snapshot["requirements"]:
        issue("error", "empty_requirements", "project.requirements",
              "Add at least one requirement before running checks.")

    referenced_inputs = set()
    assessed_models = {item["model_id"] for item in snapshot["requirements"]}
    models = {item["id"]: item for item in snapshot["models"]}
    for index, model in enumerate(snapshot["models"]):
        path = f"project.models[{index}]"
        model_type, bindings = model["type"], model["inputs"]
        if model_type == "orbital_trajectory":
            if not model.get("accuracy"):
                issue("warning", "orbital_accuracy_missing", path + ".accuracy",
                      "Declare position and velocity accuracy tolerances and their source in the model editor. Without them the trajectory is diagnostic and its requirements remain unassessed.")
            else:
                issue("warning", "orbital_accuracy_scope", path + ".accuracy",
                      "Grid agreement will be checked when calculations run. Tolerances and physical model applicability still require engineering justification.")
        referenced_inputs.update(bindings.values())
        if model_type not in MODEL_PARAMETERS:
            issue("warning", "unsupported_model", path + ".type",
                  f"No maintained deterministic adapter supports {model_type}; its requirements remain unassessed.")
        else:
            expected = MODEL_PARAMETERS[model_type]
            links = model.get("links", {})
            all_bindings = {**bindings, **links}
            if model_type == "power_energy_budget":
                from .engineering import power_parameters
                try:
                    expected = power_parameters(all_bindings)
                except (ValueError, TypeError, OverflowError) as exc:
                    issue("error", "invalid_power_profile", path + ".inputs", str(exc))
                    # Keep global unit checks useful for an unfinished profile.
                    expected = {**expected, **{name: snapshot["inputs"][identity]["unit"]
                                               for name, identity in bindings.items() if name not in expected}}
            for parameter in sorted(set(expected) - set(all_bindings)):
                issue("error", "missing_parameter", path + ".inputs." + parameter,
                      f"Bind required parameter {parameter} to a supplied input in {expected[parameter]}.")
            for parameter in sorted(set(all_bindings) - set(expected)):
                issue("error", "extra_parameter", path + ".inputs." + parameter,
                      f"Parameter {parameter} is not supported by {model_type}.")
            for parameter in expected:
                if parameter not in bindings:
                    continue
                input_id = bindings[parameter]
                actual = snapshot["inputs"][input_id]["unit"]
                if actual != expected[parameter]:
                    issue("error", "input_unit_mismatch", path + ".inputs." + parameter,
                          f"Input {input_id} uses {actual}; {parameter} requires {expected[parameter]}. No conversion is performed.")
        if model["id"] not in assessed_models:
            issue("warning", "unassessed_model", path,
                  f"Model {model['id']} has no requirement mapped to its metrics.")

    for index, requirement in enumerate(snapshot["requirements"]):
        referenced_inputs.add(requirement["limit_input"])
        model_type = models[requirement["model_id"]]["type"]
        if model_type not in _MODEL_DETAILS:
            continue  # Unsupported metric knowledge cannot be inferred.
        metrics = {name: unit for name, unit, _ in _MODEL_DETAILS[model_type][2]}
        path = f"project.requirements[{index}]"
        metric = requirement["metric"]
        if metric not in metrics:
            issue("error", "unknown_metric", path + ".metric",
                  f"Metric {metric} is not produced by {model_type}; choose a catalog metric.")
        else:
            actual = snapshot["inputs"][requirement["limit_input"]]["unit"]
            if actual != metrics[metric]:
                issue("error", "requirement_unit_mismatch", path + ".limit_input",
                      f"Limit input uses {actual}; metric {metric} requires {metrics[metric]}. No conversion is performed.")

    for index, contract in enumerate(snapshot.get("interfaces", [])):
        referenced_inputs.add(contract["target_input"])
        if contract["source"]["kind"] == "input":
            referenced_inputs.add(contract["source"]["input_id"])
            actual = snapshot["inputs"][contract["source"]["input_id"]]["unit"]
        else:
            source = contract["source"]
            details = _MODEL_DETAILS.get(models[source["model_id"]]["type"])
            metrics = {name: unit for name, unit, _ in details[2]} if details else {}
            actual = metrics.get(source["metric"])
            if actual is None:
                issue("warning", "interface_metric_unavailable", f"project.interfaces[{index}].source",
                      "This interface source metric is not supported by the maintained catalog; its comparison remains unassessed without usable saved evidence.")
        target_unit = snapshot["inputs"][contract["target_input"]]["unit"]
        if target_unit != contract["unit"] or (actual is not None and actual != contract["unit"]):
            issue("warning", "interface_unit_mismatch", f"project.interfaces[{index}]",
                  "Source, target and interface units must match exactly. This interface will remain unassessed; no conversion or coupled model execution is performed.")

    for input_id in sorted(set(snapshot["inputs"]) - referenced_inputs):
        issue("warning", "unreferenced_input", "project.inputs." + input_id,
              f"Input {input_id} is not referenced by a model or requirement.")
    return result()
