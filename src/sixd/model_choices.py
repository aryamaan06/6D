"""Explicit per-investigation Nemotron choices, never automatic routing.

Only trusted model/price variants of the existing approved configuration are
constructed. The approval identity, cumulative cap, endpoint, protocol and all
other settings remain unchanged. Selecting a choice never makes a request.
"""
from dataclasses import replace

from .model_evaluation import CANDIDATES
from .providers import ProviderError


POLICY = "sixd.explicit-investigation-model.v1"
DESCRIPTIONS = {
    "nano": "Lightweight explanations and narrowly scoped evidence questions.",
    "super": "Standard engineering investigations and follow-up checks.",
    "ultra": "Detailed investigation of related findings and evidence gaps.",
}


def choice_id(model):
    return next((item["id"] for item in CANDIDATES if item["model"] == model), None)


def candidate(choice):
    if not isinstance(choice, str):
        raise ProviderError("Choose Nano, Super or Ultra for this investigation.", code="configuration_error")
    item = next((item for item in CANDIDATES if item["id"] == choice), None)
    if item is None:
        raise ProviderError("Choose Nano, Super or Ultra for this investigation.", code="configuration_error")
    return item


def explicit_config(base, choice):
    item = candidate(choice)
    return replace(base, model=item["model"],
        input_usd_per_million_ceiling=item["input_usd_per_million"],
        output_usd_per_million_ceiling=item["output_usd_per_million"])


def permitted_variant(base, proposed):
    """Hosted operator authorization cannot be expanded through client config."""
    return proposed == base or any(proposed == explicit_config(base, item["id"])
                                   for item in CANDIDATES)


def catalog():
    return [{"id": item["id"], "label": item["label"], "model": item["model"],
             "description": DESCRIPTIONS[item["id"]], "max_job_requests": 6,
             "max_job_reservation_usd": item["per_case_cap_usd"],
             "validation_state": "current_build_not_observed", "live_validated": False,
             "whole_project_live_validated": False}
            for item in CANDIDATES]
