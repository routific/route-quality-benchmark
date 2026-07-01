"""Adapter between the Standard contract and VROOM (custom-matrix mode).

VROOM receives the instance's raw-OSRM `distances` matrix in each request, so no
OSRM/map backend is involved. Capacity/demand are mapped to VROOM's integer
amount vectors; open routes (null start/end) omit start_index/end_index; null
shift/window bounds are filled against the instance time horizon.

The Standard Instance is already hard-constrained (no soft `etas_options`) and
carries no per-vehicle speed or per-visit priority, so this adapter is a
straight structural mapping.
"""
from __future__ import annotations
import os

PROFILE = "car"
# Fill a null (open-ended) shift/window bound. 10y past the latest real time,
# staying well under uint32 for the (seconds/epoch) timestamps in the data.
_HORIZON_SLACK = 10 * 365 * 24 * 3600

# When the instance objective is minimize_vehicles, charge a fixed cost per
# vehicle *used* so VROOM consolidates routes (its default objective minimizes
# travel time, NOT the number of vehicles). VROOM maximizes assigned tasks
# lexicographically before minimizing cost, so a fixed cost — however large —
# never causes a servable visit to be dropped to save a vehicle: the hierarchy
# stays serve > vehicles > travel-time. Env-tunable.
FIXED_COST = int(os.environ.get("VROOM_FIXED_COST", "100000000"))
PER_HOUR = 3600  # VROOM default: cost per hour of travel (≈ 1 cost unit / second)


def _load_dims(vehicles):
    """Ordered capacity dimensions: scalar -> [''], typed dict -> sorted keys,
    none anywhere -> None."""
    has_scalar = False
    dim_set = set()
    for v in vehicles:
        cap = v.get("capacity")
        if cap is None:
            continue
        if isinstance(cap, dict):
            dim_set.update(cap.keys())
        else:
            has_scalar = True
    if dim_set:
        return sorted(dim_set)
    if has_scalar:
        return [""]
    return None


def _dim_value(load, dim):
    if load is None:
        return 0.0
    if isinstance(load, dict):
        return float(load.get(dim, 0.0))
    return float(load)


def _pick_scale(values):
    """Smallest factor in {1,10,100,1000} making every value integral (VROOM
    amounts are integers), so fractional demands aren't lost."""
    for scale in (1, 10, 100, 1000):
        if all(abs(v * scale - round(v * scale)) < 1e-6 for v in values):
            return scale
    return 1000


def _time_horizon(visits, vehicles):
    times = []
    for v in vehicles:
        for t in (v.get("shift_start_time"), v.get("shift_end_time")):
            if t is not None:
                times.append(t)
    for vt in visits:
        for tw in (vt.get("time_windows") or []):
            for t in (tw.get("start"), tw.get("end")):
                if t is not None:
                    times.append(t)
    return (max(times) if times else 0) + _HORIZON_SLACK


def _window(lo, hi, horizon):
    if lo is None and hi is None:
        return None
    return [lo if lo is not None else 0, hi if hi is not None else horizon]


def to_request(instance: dict) -> dict:
    """Standard Instance -> VROOM request. Vehicle/job ids are the 0-based
    indices into instance.vehicles / instance.visits, so the response maps
    straight back to indices."""
    visits = instance["visits"]
    vehicles = instance["vehicles"]
    horizon = _time_horizon(visits, vehicles)
    dims = _load_dims(vehicles)
    minimize_vehicles = bool(instance.get("minimize_vehicles"))

    scale = 1
    big = 0
    if dims is not None:
        vals = [_dim_value(v.get("capacity"), d) for v in vehicles for d in dims]
        vals += [abs(_dim_value(vt.get("demand"), d)) for vt in visits for d in dims]
        scale = _pick_scale([v for v in vals if v])
        # Uncapacitated vehicle in a capacitated instance -> effectively infinite.
        big = int(sum(abs(_dim_value(vt.get("demand"), d)) for vt in visits for d in dims) * scale) + 1

    out_vehicles = []
    for i, v in enumerate(vehicles):
        vv = {"id": i, "profile": PROFILE}
        tw = _window(v.get("shift_start_time"), v.get("shift_end_time"), horizon)
        if tw is not None:
            vv["time_window"] = tw
        if v.get("start_location") is not None:
            vv["start_index"] = v["start_location"]
        if v.get("end_location") is not None:
            vv["end_index"] = v["end_location"]
        if dims is not None:
            cap = v.get("capacity")
            vv["capacity"] = [big] * len(dims) if cap is None else \
                [int(round(_dim_value(cap, d) * scale)) for d in dims]
        if minimize_vehicles:
            vv["costs"] = {"fixed": FIXED_COST, "per_hour": PER_HOUR}
        out_vehicles.append(vv)

    out_jobs = []
    for j, vt in enumerate(visits):
        job = {"id": j, "location_index": vt["location"], "service": vt.get("duration", 0) or 0}
        tws = vt.get("time_windows") or []
        if tws:
            job["time_windows"] = [_window(tw.get("start"), tw.get("end"), horizon) for tw in tws]
        if dims is not None:
            demand = vt.get("demand")
            delivery = [max(0, int(round(_dim_value(demand, d) * scale))) for d in dims]
            pickup = [max(0, int(round(-_dim_value(demand, d) * scale))) for d in dims]
            if any(delivery):
                job["delivery"] = delivery
            if any(pickup):
                job["pickup"] = pickup
        out_jobs.append(job)

    return {"vehicles": out_vehicles, "jobs": out_jobs,
            "matrices": {PROFILE: {"durations": instance["distances"]}}}


def to_solution(instance: dict, response: dict, instance_name: str) -> dict:
    """VROOM response -> Standard Solution. Job/vehicle ids are indices."""
    routes = []
    for r in response.get("routes", []):
        steps = r.get("steps", [])
        visits = [s["id"] for s in steps if s.get("type") == "job"]
        start_time = next((s.get("arrival") for s in steps if s.get("type") == "start"), None)
        if start_time is None and steps:
            start_time = steps[0].get("arrival")
        routes.append({"vehicle": r["vehicle"], "start_time": start_time, "visits": visits})

    unserved = [u["id"] for u in response.get("unassigned", [])]
    summary = response.get("summary") or {}
    runtime_ms = (summary.get("computing_times") or {}).get("solving")
    return {
        "instance": instance_name,
        "solver": "vroom",
        "routes": routes,
        "unserved": unserved,
        "runtime_ms": runtime_ms,
        "meta": {k: summary.get(k) for k in ("routes", "unassigned", "duration", "cost")},
    }
