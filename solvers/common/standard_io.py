"""Shared helpers for reading Standard Instances and writing Standard Solutions.

Every solver harness in this repo consumes a Standard Instance (see
docs/standard-io-contract.md) and emits a Standard Solution, so metrics can be
recomputed from `(instance, solution)` alone.
"""
from __future__ import annotations
import gzip
import json


def load_instance(path: str) -> dict:
    """Load a Standard Instance from a `.json` or `.json.gz` file."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as f:
        return json.load(f)


def write_solution(path: str, solution: dict) -> None:
    """Write a Standard Solution (minified JSON)."""
    with open(path, "w") as f:
        json.dump(solution, f, separators=(",", ":"), ensure_ascii=False)


def check_coverage(instance: dict, solution: dict) -> dict:
    """Sanity-check a solution against its instance: every visit index must
    appear exactly once across routes ∪ unserved."""
    n = len(instance["visits"])
    served: list[int] = []
    for r in solution["routes"]:
        served += r["visits"]
    served_set = set(served) | set(solution["unserved"])
    return {
        "n_visits": n,
        "complete": served_set == set(range(n)),
        "has_duplicates": len(served) != len(set(served)),
    }
