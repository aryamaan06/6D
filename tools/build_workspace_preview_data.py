"""Regenerate recorded, nonflight inputs/results for the isolated design preview.

Run from a checkout with Python; no network, inference, or credentials are used.
The real maintained adapters produce every metric. The preview may replay only
the supplied snapshot grid; this is not a browser solver or a mission simulator.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sixd.engineering import evaluate_models
from sixd.lifecycle import compare_reviews, review_project, validate_project, verify_review
from sixd.project_examples import example_projects


REFERENCE_SOURCES = {
    "propulsion": [
        {"title": "NASA: Ideal rocket equation", "url": "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ideal-rocket-equation/"},
        {"title": "NASA: Specific impulse", "url": "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/specific-impulse/"},
    ],
    "mount": [
        {"title": "MIT: Beam bending stresses", "url": "https://web.mit.edu/course/3/3.11/www/modules/bstress.pdf"},
        {"title": "MIT: Beam deflection derivation", "url": "https://ocw.mit.edu/courses/3-052-nanomechanics-of-materials-and-biomaterials-spring-2007/d8d2ffa0503ad0adf0edb741ddb4e4c8_lec2_appendix.pdf"},
    ],
    "thermal": [
        {"title": "NASA: Spacecraft thermal control", "url": "https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/"},
        {"title": "NIST: Stefan-Boltzmann constant", "url": "https://physics.nist.gov/cgi-bin/cuu/Value?sigma%7Csearch_for=stefan+boltzmann"},
    ],
    "atmospheric_load": [
        {"title": "NASA: Drag equation", "url": "https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/drag-equation/"},
    ],
}


def record(project: dict) -> dict:
    """Capture intact input, model result and verified review records."""
    clean = validate_project(deepcopy(project))
    results = evaluate_models(clean)
    review = review_project(clean, results)
    assert verify_review(review)
    counts = Counter(finding["status"] for finding in review["findings"].values())
    temperature = results["thermal"]["metrics"]["equilibrium_temperature"]["value"]
    limit = clean["inputs"]["maximum_temperature"]["value"]
    return {
        "project": clean,
        "model_results": results,
        "review": review,
        "summary": {
            "heat_input_w": clean["inputs"]["heat_input"]["value"],
            "maximum_temperature_k": limit,
            "equilibrium_temperature_k": temperature,
            "temperature_margin_k": limit - temperature,
            "requirement_counts": {status: counts[status] for status in ("met", "not_met", "not_assessed")},
        },
    }


def build_fixture() -> dict:
    baseline = deepcopy(example_projects()["baseline"])
    revised = deepcopy(baseline)
    revised["revision"] = "2"
    revised["inputs"]["heat_input"]["value"] = 600
    # Unlike the source example's revised case, thrust is deliberately unchanged.
    assert [key for key in baseline["inputs"] if baseline["inputs"][key] != revised["inputs"][key]] == ["heat_input"]

    control_gap = deepcopy(revised)
    control_gap["revision"] = "3"
    control_gap["inputs"]["maximum_tracking_error"] = {
        "value": 10, "unit": "m", "source": "Constructed demonstration input; not measured hardware data."
    }
    control_gap["models"].append({"id": "control", "type": "unsupported_closed_loop_gnc", "inputs": {}})
    control_gap["requirements"].append({
        "id": "control_tracking", "title": "Unimplemented control-performance requirement",
        "model_id": "control", "metric": "tracking_error", "operator": "<=",
        "limit_input": "maximum_tracking_error", "critical": True,
    })
    variants = {name: record(project) for name, project in (
        ("baseline", baseline), ("revised", revised), ("control_gap", control_gap)
    )}
    snapshots = {}
    for heat in (200, 400, 600, 800):
        for limit in (300, 320, 350):
            project = deepcopy(baseline)
            project["revision"] = f"preview-heat{heat}-limit{limit}"
            project["inputs"]["heat_input"]["value"] = heat
            project["inputs"]["maximum_temperature"]["value"] = limit
            snapshot = record(project)
            snapshot["change_from_baseline"] = compare_reviews(variants["baseline"]["review"], snapshot["review"])
            snapshots[f"heat{heat}_limit{limit}"] = snapshot

    comparisons = {
        "baseline_to_revised": compare_reviews(variants["baseline"]["review"], variants["revised"]["review"]),
        "baseline_to_control_gap": compare_reviews(variants["baseline"]["review"], variants["control_gap"]["review"]),
        "revised_to_control_gap": compare_reviews(variants["revised"]["review"], variants["control_gap"]["review"]),
    }
    assert comparisons["baseline_to_revised"]["previous_evidence_needs_rechecking"] == ["thermal_limit"]
    assert variants["baseline"]["summary"]["requirement_counts"] == {"met": 6, "not_met": 0, "not_assessed": 0}
    assert variants["revised"]["summary"]["requirement_counts"] == {"met": 5, "not_met": 1, "not_assessed": 0}
    assert variants["control_gap"]["summary"]["requirement_counts"] == {"met": 5, "not_met": 1, "not_assessed": 1}

    sources = ["src/sixd/project_examples.py", "src/sixd/engineering.py", "src/sixd/lifecycle.py"]
    fixture = {
        "schema": "sixd.workspace-preview-reference.v1",
        "provenance": {
            "kind": "constructed_nonflight_reference",
            "generator": "tools/build_workspace_preview_data.py",
            "execution": "Recorded maintained deterministic adapters; no model inference or browser solver.",
            "source_example": "sixd.project_examples.example_projects()['baseline']",
            "variant_definitions": {
                "baseline": "Unchanged source baseline: six requirements, heat input 200 W, temperature limit 320 K.",
                "revised": "Copy of baseline, revision 2, only heat input changed to 600 W. Thrust remains 200 N.",
                "control_gap": "Copy of revised, revision 3, plus an explicit unsupported GNC model and seventh requirement.",
            },
            "snapshot_grid": {"heat_input_w": [200, 400, 600, 800], "maximum_temperature_k": [300, 320, 350]},
            "limitations": [
                "Illustrative component inputs and declared limits; not a spacecraft mission or flight readiness assessment.",
                "Only the explicit bindings drive change impact; no coupled physics or automatic heat-from-thrust inference.",
                "The heat curve shows steady equilibrium at each input, not a thermal transient or elapsed-time simulation.",
                "The twelve recorded combinations support a constrained preview; other values require a fresh backend calculation.",
                "The control-gap variant is a separate snapshot; baseline has six requirements and no GNC evidence.",
            ],
            "source_sha256": {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
        },
        "reference_sources": REFERENCE_SOURCES,
        "variants": variants,
        "snapshots": snapshots,
        "comparisons": comparisons,
        "thermal_curve": [
            {"heat_input_w": heat, "equilibrium_temperature_k": snapshots[f"heat{heat}_limit320"]["summary"]["equilibrium_temperature_k"]}
            for heat in (200, 400, 600, 800)
        ],
    }
    return fixture


def main() -> None:
    fixture = build_fixture()
    destination = ROOT / "design" / "fixtures" / "workspace-reference.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(fixture, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Recorded {len(fixture['variants'])} variants and {len(fixture['snapshots'])} snapshots: {destination}")
    print("No inference, network access, credentials or ledger changes.")


if __name__ == "__main__":
    main()
