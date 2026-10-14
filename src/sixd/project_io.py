"""Strict JSON input and append-only lifecycle review snapshots; no code loading."""
from datetime import datetime, timezone
import json
from pathlib import Path

from .lifecycle import verify_review

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_REVIEW_BYTES = 16 * 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}.")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Nonstandard JSON numeric constant {value} is not allowed.")


def read_json(path, *, maximum_bytes=MAX_JSON_BYTES):
    with Path(path).open("rb") as source:
        data = source.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        raise ValueError("The JSON input exceeds the local size limit.")
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


def save_review(review, directory):
    verify_review(review)
    encoded = (json.dumps(review, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_REVIEW_BYTES:
        raise ValueError("The generated review exceeds the sixteen-megabyte snapshot limit.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"review-{review['digest'][:20]}-{stamp}.json"
    with path.open("xb") as target:
        target.write(encoded)
    return path


def read_review(path):
    review = read_json(path, maximum_bytes=MAX_REVIEW_BYTES)
    verify_review(review)
    return review
