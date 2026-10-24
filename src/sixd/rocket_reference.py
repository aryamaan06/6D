"""Read-only guide for the exact constructed rocket reference.

The caller supplies a verified WorkspaceStore view. This projection does not
calculate physics, create revisions or infer a project is a complete rocket.
Guided edits are offered only for unchanged reference definitions and sources.
"""
from copy import deepcopy

from . import engineering, lifecycle
from .project_examples import integrated_rocket_review


SUPPORTED_IDS = ("propulsion", "vertical_flight", "atmospheric_load", "mount", "thermal")
SCOPE = [
    "Five bounded calculations share explicit engine and mass inputs. This is a constructed reference, not measured hardware or a complete rocket design.",
    "Maximum sampled flight speed feeds a separate reference-density drag screen, then a declared transverse static cantilever load. These are one-way scalar links, not simultaneous physics or whole-vehicle structural verification.",
    "The independent 200 W steady radiator case does not predict ascent aeroheating. Ideal budget burn duration differs from full-propellant flight burn duration.",
    "Rocket launch guidance, navigation and control remain unassessed. No staging, horizontal steering, reentry, landing or launch authorization is supplied by this reference.",
]
STEPS = ["Baseline · 20,000 N", "Reduced thrust · 11,000 N", "Restore thrust · 20,000 N"]


def _configuration(project):
    result = lifecycle.validate_project(project)
    for key in ("project_id", "name", "revision"):
        result.pop(key)
    return result


def _reference_thrust(project):
    """Exact full-definition match, permitting display metadata and two thrusts."""
    try:
        candidate = _configuration(project)
        thrust = candidate["inputs"]["thrust"]["value"]
        if thrust not in (20000, 11000):
            return None
        candidate["inputs"]["thrust"]["value"] = 20000
        return thrust if candidate == _configuration(integrated_rocket_review()) else None
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def _current_run(view):
    run = view.get("run")
    if not run or run.get("stale", True):
        return None
    review = run.get("review", {})
    if (run.get("project_id") != view["project_id"]
            or run.get("revision") != view["revision"]
            or review.get("project") != view["project"]
            or review.get("verification_sources") != lifecycle._verification_sources()
            or review.get("adapter_versions") != engineering.MODEL_VERSIONS):
        return None
    return run


def _restored_after_reduced(view, run):
    prior = view.get("prior_run")
    if not run or not prior:
        return False
    review, current = prior.get("review", {}), run["review"]
    # Prior revisions have stale=True in workspace views because their design
    # differs. Compare source vectors, not that deliberately historical flag.
    return (prior.get("project_id") == view["project_id"]
            and isinstance(prior.get("revision"), int)
            and prior["revision"] < view["revision"]
            and _reference_thrust(review.get("project")) == 11000
            and review.get("verification_sources") == current["verification_sources"]
            and review.get("adapter_versions") == current["adapter_versions"])


def profile_from_view(view):
    """Project the reference guide from one captured, verified saved view."""
    result = dict(schema="sixd.rocket-reference-profile.v1", context="saved",
                  project_id=view["project_id"], revision=view["revision"],
                  run_id=None, recognized=False, stage=None, can_stage=False,
                  next_thrust=None, action_label=None, executed_model_ids=[],
                  reused_model_ids=[], model_origins={})
    thrust = _reference_thrust(view.get("project"))
    if thrust is None:
        result["reason"] = "This configuration differs from the constructed rocket reference. Normal draft editing remains available; no guided change is offered."
        return result

    run = _current_run(view)
    stage = "reduced" if thrust == 11000 else "baseline"
    if thrust == 20000 and _restored_after_reduced(view, run):
        stage = "corrected"
    result.update(recognized=True, stage=stage, thrust=thrust,
                  title={"baseline":"Baseline configuration", "reduced":"Reduced-thrust configuration",
                         "corrected":"Restored-thrust configuration"}[stage],
                  scope=deepcopy(SCOPE), steps=list(STEPS),
                  next_thrust={"baseline":11000,"reduced":20000,"corrected":None}[stage],
                  action_label={"baseline":"Stage reduced thrust", "reduced":"Stage thrust correction", "corrected":None}[stage])
    if run:
        result.update(run_id=run["run_id"],
                      executed_model_ids=[x for x in run["executed_model_ids"] if x in SUPPORTED_IDS],
                      reused_model_ids=[x for x in run["reused_model_ids"] if x in SUPPORTED_IDS],
                      model_origins={x:deepcopy(run["model_origins"][x]) for x in SUPPORTED_IDS if x in run["model_origins"]})
    if view["revision"] != view["latest_revision"]:
        result["reason"] = "Historical revision. Open the latest saved revision before staging a change."
    elif not run:
        result["reason"] = "Run checks for this saved revision before staging the next reference change. Earlier or stale evidence is not a current result."
    elif stage == "corrected":
        result["reason"] = "Thrust is restored after the recorded reduced-thrust case. Inspect the actual findings and remaining unassessed scope below; this does not establish whole-mission readiness."
    else:
        result["can_stage"] = True
        result["reason"] = ("Stage only the thrust change from 20,000 N to 11,000 N. Preview its dependencies, save the revision and rerun affected checks."
                            if stage == "baseline" else
                            "Restore thrust from 11,000 N to 20,000 N. Keep the declared criteria fixed; save and rerun to see whether the burnout-altitude finding changes.")
    return result
