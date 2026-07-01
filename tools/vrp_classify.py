"""Classify a standard VRP instance into a problem type from its structure.

The type is derived purely from the instance content (no external metadata),
so anyone with a standard instance file can reproduce the classification.

Taxonomy (by constraint presence):
  - pdp / pdptw : any visit has a pickup-delivery precedence
  - cvrptw      : vehicles have capacity AND visits have time windows
  - cvrp        : vehicles have capacity, no time windows
  - vrptw       : time windows, no capacity
  - vrp         : multi-vehicle, no capacity, no time windows
  - tsp         : single vehicle, no capacity, no time windows
"""
from __future__ import annotations


def _has_capacity(instance: dict) -> bool:
    return any(v.get("capacity") is not None for v in instance.get("vehicles", []))


def _has_time_windows(instance: dict) -> bool:
    return any(len(v.get("time_windows") or []) > 0 for v in instance.get("visits", []))


def _has_pdp(instance: dict) -> bool:
    # precedence is serialized as the string "None" when absent, or an object when present
    return any(v.get("precedence") not in (None, "None") for v in instance.get("visits", []))


def classify(instance: dict) -> str:
    has_capacity = _has_capacity(instance)
    has_tw = _has_time_windows(instance)
    has_pdp = _has_pdp(instance)
    single_vehicle = len(instance.get("vehicles", [])) == 1

    if has_pdp:
        return "pdptw" if has_tw else "pdp"
    if has_capacity and has_tw:
        return "cvrptw"
    if has_capacity:
        return "cvrp"
    if has_tw:
        return "vrptw"
    return "tsp" if single_vehicle else "vrp"


# Ordered list of every type this classifier can emit (for directory scaffolding / docs).
ALL_TYPES = ["tsp", "vrp", "cvrp", "vrptw", "cvrptw", "pdp", "pdptw"]
