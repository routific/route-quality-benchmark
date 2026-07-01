"""Adapter between the Standard contract and the jsprit HTTP service.

The Java service (unchanged from Routific's internal harness) speaks its own
request shape (`vehicles`/`services`/`travel_times`), so — like VROOM — we adapt
client-side rather than recompile Java.

jsprit limitations reflected here:
  - single capacity dimension: typed (multi-dim) capacity/demand is collapsed to a
    scalar (sum of dimensions). Documented in README.
  - a vehicle needs a start depot; a null start_location falls back to end_location
    (or 0), since jsprit has no "open start".
"""
from __future__ import annotations

_BIG_TW = 10 ** 12  # jsprit needs a concrete latest time; stand-in for "no upper bound"


def _scalar(load) -> float:
    """Collapse a Standard scalar|typed-dict|null load to a single jsprit value."""
    if load is None:
        return 0.0
    if isinstance(load, dict):
        return float(sum(load.values()))
    return float(load)


def to_request(instance: dict, time_limit_ms: int | None = None) -> dict:
    vehicles = []
    for i, v in enumerate(instance["vehicles"]):
        start = v.get("start_location")
        if start is None:  # jsprit requires a start depot
            start = v.get("end_location") if v.get("end_location") is not None else 0
        se = v.get("shift_end_time")
        vehicles.append({
            "id": str(i),
            "start_index": start,
            "end_index": v.get("end_location"),       # null -> open route (no return)
            "capacity": _scalar(v.get("capacity")),   # <=0 -> unlimited (jsprit)
            "earliest_start": float(v.get("shift_start_time") or 0),
            "latest_end": (float(se) if se is not None else None),
        })

    services = []
    for j, vt in enumerate(instance["visits"]):
        tws = vt.get("time_windows") or []
        tw = None
        if tws:
            lo = min((w["start"] for w in tws if w.get("start") is not None), default=0)
            hi = max((w["end"] for w in tws if w.get("end") is not None), default=_BIG_TW)
            tw = {"earliest": float(lo), "latest": float(hi)}
        services.append({
            "id": str(j),
            "location_index": vt["location"],
            "duration": float(vt.get("duration") or 0),
            "demand": _scalar(vt.get("demand")),
            "time_window": tw,
        })

    req = {
        "vehicles": vehicles,
        "services": services,
        "travel_times": instance["distances"],
        "minimize_vehicles": bool(instance.get("minimize_vehicles")),
    }
    if time_limit_ms:
        req["time_limit_ms"] = int(time_limit_ms)
    return req


def to_solution(instance: dict, response: dict, instance_name: str, runtime_ms) -> dict:
    """jsprit response (routes with string ids) -> Standard Solution. Vehicle/
    service ids are the stringified indices, so they map straight back."""
    routes = []
    for r in response.get("routes", []):
        routes.append({
            "vehicle": int(r["vehicle_id"]),
            "start_time": int(round(r.get("start_time", 0))),
            "visits": [int(s) for s in r.get("service_ids", [])],
        })
    unserved = [int(s) for s in response.get("unserved_ids", [])]
    return {
        "instance": instance_name,
        "solver": "jsprit",
        "routes": routes,
        "unserved": unserved,
        "runtime_ms": runtime_ms,
        "meta": {},
    }
