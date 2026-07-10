"""Route-quality metrics computed from a (Standard Instance, Standard Solution) pair.

The definitions match the analyzer Routific uses internally to evaluate its own engine, so the
public numbers line up with the internal ones. Everything is recomputed from the two JSON files
alone, so results are independently reproducible. See analysis/README.md for definitions +
grounding (Rossit et al. 2019).

Metrics:
  travel_time              Σ per-route travel time over matrix legs (incl. depot legs)
  idle_time                Σ waiting for time windows to open
  num_vehicles             non-empty routes
  workload_imbalance       Σ over routes |route.num_visits − average_route_length|
  route_duration_variance  max(service+travel+idle) − min(...) over routes (a RANGE, despite the name)
  intra_route_crossings    self-crossings: legs = depot→first + visit→visit + last→depot;
                           non-consecutive pairs, excluding the first↔last wrap
  inter_route_crossings_*  visit→visit legs only, counted only between ADJACENT routes

Known fidelity gap vs the internal analyzer: route adjacency implements the nearest-neighbor rule
+ full-connect, but not the internal refinement that reroutes adjacency edges away from route pairs
that are incompatible by vehicle type, capacity, or time windows.
"""
from __future__ import annotations

_EPS = 1e-12


# --------------------------------------------------------------------------- geometry
def _orient(a, b, c) -> int:
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (v > _EPS) - (v < -_EPS)


def _crosses(s1, s2) -> bool:
    (p, q), (r, s) = s1, s2
    return _orient(r, s, p) != _orient(r, s, q) and _orient(p, q, r) != _orient(p, q, s)


def _dedup(seq):
    out = []
    for x in seq:
        if not out or x != out[-1]:
            out.append(x)
    return out


def _pt(instance, loc_id):  # (lat, lng)
    c = instance["locations"][loc_id]
    return (c["lat"], c["lng"])


def _segments(pts):
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


# --------------------------------------------------------------------------- adjacency
def _vehicle_adjacency(instance, routes):
    """Route adjacency: nearest-neighbor rule + full-connect (no incompatibility rerouting).

    routes: list of (vehicle_idx, permutation) for NON-EMPTY routes. Returns a list of
    neighbor-index sets over those routes.
    """
    n = len(routes)
    adj = [set() for _ in range(n)]
    if n <= 1:
        return adj

    coords, owner, all_v = {}, {}, []
    for ri, (_, perm) in enumerate(routes):
        for vi in perm:
            coords[vi] = _pt(instance, instance["visits"][vi]["location"])
            owner[vi] = ri
            all_v.append(vi)

    def d2(a, b):
        return (coords[a][0] - coords[b][0]) ** 2 + (coords[a][1] - coords[b][1]) ** 2

    # each visit's nearest visit assigned to a different route -> bidirectional route edge
    for vi in all_v:
        ri = owner[vi]
        nearest = min((vj for vj in all_v if owner[vj] != ri), key=lambda vj: d2(vi, vj), default=None)
        if nearest is not None:
            rj = owner[nearest]
            adj[ri].add(rj)
            adj[rj].add(ri)

    # make_fully_connected: bridge disconnected components by the closest cross-component visit pair
    def components():
        seen, comps = set(), []
        for start in range(n):
            if start in seen:
                continue
            stack, comp = [start], set()
            while stack:
                u = stack.pop()
                if u in seen:
                    continue
                seen.add(u); comp.add(u)
                stack.extend(adj[u] - seen)
            comps.append(comp)
        return comps

    comps = components()
    while len(comps) > 1:
        a, b = comps[0], comps[1]
        best = None
        for vi in all_v:
            if owner[vi] not in a:
                continue
            for vj in all_v:
                if owner[vj] not in b:
                    continue
                dd = d2(vi, vj)
                if best is None or dd < best[0]:
                    best = (dd, owner[vi], owner[vj])
        _, ra, rb = best
        adj[ra].add(rb); adj[rb].add(ra)
        comps = components()
    return adj


# --------------------------------------------------------------------------- metrics
def _window_start(visit):
    tws = visit.get("time_windows") or []
    return min((w["start"] for w in tws if w.get("start") is not None), default=None)


def compute(instance: dict, solution: dict) -> dict:
    visits, vehicles, matrix = instance["visits"], instance["vehicles"], instance["distances"]
    routes = [(r["vehicle"], r["visits"]) for r in solution["routes"] if r.get("visits")]

    travel = idle = intra = 0
    shift_times, route_lengths = [], []
    cluster_lines = []  # visit→visit legs per route (inter-route crossings)

    for vk, perm in routes:
        v = vehicles[vk]
        # timeline: travel / idle / service
        t = v.get("shift_start_time") or 0
        prev = v.get("start_location")
        rt_travel = rt_idle = rt_service = 0
        for vi in perm:
            loc = visits[vi]["location"]
            if prev is not None:
                leg = matrix[prev][loc]; travel += leg; rt_travel += leg; t += leg
            lo = _window_start(visits[vi])
            if lo is not None and t < lo:
                wait = lo - t; idle += wait; rt_idle += wait; t = lo
            svc = visits[vi].get("duration") or 0; rt_service += svc; t += svc
            prev = loc
        end = v.get("end_location")
        if prev is not None and end is not None:
            travel += matrix[prev][end]; rt_travel += matrix[prev][end]
        shift_times.append(rt_service + rt_travel + rt_idle)
        route_lengths.append(len(perm))

        # intra-route self-crossings: depot→first + visit→visit + last→depot
        ids = []
        if v.get("start_location") is not None:
            ids.append(v["start_location"])
        ids += [visits[i]["location"] for i in perm]
        if v.get("end_location") is not None:
            ids.append(v["end_location"])
        legs = _segments([_pt(instance, i) for i in _dedup(ids)])
        last = len(legs) - 1
        for i in range(len(legs)):
            for j in range(i + 2, len(legs)):
                if i == 0 and j == last:      # exclude the first↔last wrap
                    continue
                if _crosses(legs[i], legs[j]):
                    intra += 1
        cluster_lines.append(_segments([_pt(instance, i) for i in _dedup([visits[i]["location"] for i in perm])]))

    # inter-route crossings — only between adjacent routes, visit-legs only
    adj = _vehicle_adjacency(instance, routes)
    inter_sum = 0
    per_route = [0] * len(routes)
    for a in range(len(routes)):
        for b in adj[a]:
            if a >= b:
                continue
            c = sum(1 for l0 in cluster_lines[a] for l1 in cluster_lines[b] if _crosses(l0, l1))
            inter_sum += c
    for a in range(len(routes)):        # max is per-leg over adjacent routes
        for l0 in cluster_lines[a]:
            cnt = sum(1 for b in adj[a] for l1 in cluster_lines[b] if _crosses(l0, l1))
            per_route[a] = max(per_route[a], cnt)
    inter_max = max(per_route) if per_route else 0

    n = len(routes)
    avg_len = (sum(route_lengths) / n) if n else 0.0
    workload_imbalance = sum(abs(rl - avg_len) for rl in route_lengths)
    duration_range = (max(shift_times) - min(shift_times)) if shift_times else 0

    return {
        "travel_time": travel,
        "num_vehicles": n,
        "num_unserved": len(solution.get("unserved", [])),
        "inter_route_crossings_sum": inter_sum,
        "inter_route_crossings_max": inter_max,
        "intra_route_crossings": intra,
        "workload_imbalance": round(workload_imbalance, 2),
        "route_duration_variance": duration_range,
        "idle_time": idle,
        "runtime_ms": solution.get("runtime_ms"),
    }
