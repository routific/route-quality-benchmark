#!/usr/bin/env python3
"""Solve a cached benchmark instance (engine `InstanceWrapper` JSON) with PyVRP,
reusing the engine's own travel-time matrix so the two solvers see the *same*
problem (same travel times, shifts, time windows, capacities) and can be compared
apples-to-apples. No OSRM/routing backend is involved.

PyVRP is a hybrid genetic search solver for hard-constrained VRPs (CVRP, VRPTW,
prize-collecting, multi-depot). The benchmark crate zeroes every soft-constraint
allowance before solving (a fair cross-solver comparison), so PyVRP always faces
hard time windows + hard capacity — exactly its sweet spot. No soft-penalty
modeling is needed (unlike the OR-Tools harness).

Mapping (engine -> PyVRP Model)
  distances[i][j]        -> edge duration (per profile = matrix / speed)
  vehicle.speed          -> one routing profile per distinct speed
  vehicle.start/end_loc  -> per-vehicle start/end depot (null => shared open depot
                            with 0-cost edges, i.e. a free open route end)
  vehicle.shift_*_time   -> vehicle_type tw_early / tw_late (hard shift window)
  vehicle.strict_start   -> start_late pinned to shift_start (fixed departure)
  vehicle.capacity       -> vehicle_type capacity (one load dimension per type)
  visit.location         -> client location (into the shared matrix)
  visit.duration         -> client service_duration
  visit.time_windows     -> client tw_early / tw_late (multi-window => enclosing span)
  visit.demand           -> client delivery (>0) / pickup (<0)
  visit.priority         -> client prize = priority * BIG, required=False (droppable;
                            dropping is lexicographically dominant, as in the engine)
  secondary_objective.minimize_vehicles -> per-vehicle fixed_cost (best-effort fleet
                            minimization; PyVRP has no native lexicographic objective)

NOT modeled (reported in meta.unmodeled, still solved): breaks, minimum_visits,
vehicle/visit types (skills), inventory, precedence/pickup-delivery pairs,
multiple disjoint time windows per visit (relaxed to their enclosing span).

The engine's exact penalty *weights* live in an external crate, so absolute cost
is not comparable across solvers. Compare quality metrics instead: unassigned
(weighted by priority), travel time, vehicles used.

If PyVRP's best solution is infeasible (its prize can outweigh the capped
feasibility penalty on instances that REQUIRE dropping clients — e.g. total demand
> fleet capacity, or shifts too short to cover every visit), we don't discard it;
we drop the minimal violating clients per route to recover a feasible solution
(meta.repaired). Only a truly empty result (best is None) stays code 2.

Exit codes: 0 = solved (possibly repaired), 1 = error, 2 = no solution produced.
"""
import argparse
import glob
import json
import math
import os
import sys
import time

from pyvrp import Model
from pyvrp.stop import MaxRuntime

# 10 years of slack past the latest real timestamp; upper bound for open shifts /
# half-open windows. Stays well under int64 for our ~1.7e9 timestamps.
HORIZON_SLACK = 10 * 365 * 24 * 3600

# Prize for serving a droppable visit. Two competing requirements:
#   * serving any FEASIBLE visit must beat dropping it  -> a high floor, well above
#     the marginal routing cost of an insertion (~1e3 s).
#   * the prize must stay under PyVRP's auto-escalating feasibility-penalty cap, or
#     PyVRP keeps a high-prize *infeasible* solution (serving a visit while
#     violating its time window / capacity) instead of dropping it (empirically the
#     cap is ~1e5-1e6 on tight instances).
# Engine priorities span 1..1e4 — far wider than this usable band — so we can't
# scale linearly. Every visit gets PRIZE_FLOOR (serve-when-feasible) plus a
# priority bonus, the whole thing capped at PRIZE_CAP for relative ordering without
# breaking feasibility. Env-overridable for tuning.
PRIZE_FLOOR = int(os.environ.get("PYVRP_PRIZE_FLOOR", "20000"))
PRIZE_PER_PRIORITY = int(os.environ.get("PYVRP_PRIZE_STEP", "160"))
PRIZE_CAP = int(os.environ.get("PYVRP_PRIZE_CAP", "100000"))


def _prize(priority):
    return min(PRIZE_CAP, PRIZE_FLOOR + max(0, priority) * PRIZE_PER_PRIORITY)


# When the instance's objective is to minimize the fleet (secondary_objective.
# minimize_vehicles), charge a fixed cost per vehicle *used* so PyVRP consolidates
# routes. PyVRP has no native lexicographic min-vehicles objective, so this is a
# best-effort bias: it must stay BELOW PRIZE_FLOOR, or PyVRP would rather drop a
# visit than open a vehicle to serve it — the hierarchy must stay serve(prize) >
# vehicles(fixed_cost) > distance. Because the prize is itself capped under PyVRP's
# feasibility-penalty ceiling, fixed_cost can't dominate arbitrarily large routing
# costs, so very large instances may not minimize the fleet strictly. Env-tunable.
VEHICLE_FIXED_COST = int(os.environ.get("PYVRP_FIXED_COST", "15000"))


# ---------------------------------------------------------------------------
# instance helpers (shared shape with benchmark/ortools/solve.py)
# ---------------------------------------------------------------------------
def _load_dims(vehicles):
    """Ordered capacity dimension names. Scalar capacities -> ['']. Dict (typed)
    capacities -> sorted union of keys. No capacities anywhere -> None."""
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
    """Read one dimension out of a scalar-or-dict load (0.0 if absent/null)."""
    if load is None:
        return 0.0
    if isinstance(load, dict):
        return float(load.get(dim, 0.0))
    return float(load)


def _pick_scale(values):
    """Smallest factor in {1,10,100,1000} making every value integral, so
    fractional demands/capacities survive the cast to PyVRP ints."""
    vals = [v for v in values if v]
    for scale in (1, 10, 100, 1000):
        if all(abs(v * scale - round(v * scale)) < 1e-6 for v in vals):
            return scale
    return 1000


def _horizon(visits, vehicles):
    times = [0]
    for v in vehicles:
        for t in (v.get("shift_start_time"), v.get("shift_end_time")):
            if t is not None:
                times.append(t)
    for vt in visits:
        for tw in (vt.get("time_windows") or []):
            for t in (tw.get("start"), tw.get("end")):
                if t is not None:
                    times.append(t)
    return max(times) + HORIZON_SLACK


def _visit_window(vt, horizon):
    """(lo, hi) enclosing span for a visit's time windows; defaults [0, horizon]."""
    tws = vt.get("time_windows") or []
    if not tws:
        return 0, horizon
    lo = min((tw["start"] for tw in tws if tw.get("start") is not None), default=0)
    hi = max((tw["end"] for tw in tws if tw.get("end") is not None), default=horizon)
    return lo, hi


def build_and_solve(instance, time_limit_ms, log=lambda *_: None):
    """Build the PyVRP model for a *prepared* instance and solve it. Returns
    (summary_dict, meta_dict). summary['code'] is 0 solved / 2 no-solution."""
    visits = instance["visits"]
    vehicles = instance["vehicles"]
    matrix = instance["distances"]
    if not isinstance(matrix, list) or (matrix and not isinstance(matrix[0], list)):
        raise ValueError("distances is not a dense NxN matrix (sparse not supported)")
    etas = instance.get("etas_options") or {}
    allow_overload = bool(etas.get("allow_capacity_overload"))
    minimize_vehicles = bool((instance.get("secondary_objective") or {}).get("minimize_vehicles"))
    fixed_cost = VEHICLE_FIXED_COST if minimize_vehicles else 0

    V = len(visits)
    K = len(vehicles)
    horizon = _horizon(visits, vehicles)

    # --- capacity dimensions + integer scaling for fractional loads ---
    dims = _load_dims(vehicles)
    scale = 1
    big_cap = []
    if dims is not None:
        vals = []
        for v in vehicles:
            for d in dims:
                vals.append(_dim_value(v.get("capacity"), d))
        for vt in visits:
            for d in dims:
                vals.append(abs(_dim_value(vt.get("demand"), d)))
        scale = _pick_scale(vals)
        # Non-binding capacity for uncapacitated vehicles / allow_overload.
        big_cap = [
            int(sum(abs(_dim_value(vt.get("demand"), d)) for vt in visits) * scale) + 1
            for d in dims
        ]

    m = Model()

    # --- one routing profile per distinct vehicle speed (time = matrix / speed) ---
    speeds = [round(float(v.get("speed", 1.0) or 1.0), 4) for v in vehicles]
    profile_by_speed = {sp: m.add_profile() for sp in sorted(set(speeds))}

    # --- depots: created BEFORE any client so client location indices are
    #     contiguous after the depots (visit_idx = location_idx - num_depots).
    #     One depot per distinct vehicle start/end engine-location, plus a shared
    #     "open" depot (0-cost edges) for null start/end (open routes).
    depot_by_loc = {}
    depot_eng = []        # engine location (or None for the open depot), in order
    open_depot = [None]

    def get_depot(loc):
        if loc is None:
            if open_depot[0] is None:
                open_depot[0] = m.add_depot(x=0, y=0, name="open")
                depot_eng.append(None)
            return open_depot[0]
        if loc not in depot_by_loc:
            depot_by_loc[loc] = m.add_depot(x=0, y=0, tw_early=0, tw_late=horizon,
                                            name=f"d{loc}")
            depot_eng.append(loc)
        return depot_by_loc[loc]

    veh_start = [get_depot(v.get("start_location")) for v in vehicles]
    veh_end = [get_depot(v.get("end_location")) for v in vehicles]
    num_depots = len(depot_eng)

    # --- one vehicle type per vehicle (so route.vehicle_type() == vehicle index) ---
    for k, v in enumerate(vehicles):
        cap = []
        if dims is not None:
            c = v.get("capacity")
            if c is None or allow_overload:
                cap = list(big_cap)
            else:
                cap = [int(round(_dim_value(c, d) * scale)) for d in dims]
        ss = v.get("shift_start_time")
        se = v.get("shift_end_time")
        m.add_vehicle_type(
            num_available=1,
            capacity=cap,
            start_depot=veh_start[k],
            end_depot=veh_end[k],
            tw_early=ss if ss is not None else 0,
            tw_late=se if se is not None else horizon,
            # Strict start pins departure to shift_start (tw_early == start_late).
            start_late=ss if (ss is not None and v.get("strict_start")) else None,
            fixed_cost=fixed_cost,  # >0 only when minimizing the fleet
            unit_distance_cost=0,   # objective is travel *time*, not distance
            unit_duration_cost=1,
            profile=profile_by_speed[speeds[k]],
            name=f"veh{k}",
        )

    # --- clients: one per visit, all droppable (prize = priority * BIG) ---
    multi_tw = 0
    for i, vt in enumerate(visits):
        if len((vt.get("time_windows") or [])) > 1:
            multi_tw += 1
        lo, hi = _visit_window(vt, horizon)
        delivery, pickup = [], []
        if dims is not None:
            for d in dims:
                val = int(round(_dim_value(vt.get("demand"), d) * scale))
                delivery.append(max(0, val))
                pickup.append(max(0, -val))
        prio = int(round(vt.get("priority", 1) or 0))
        m.add_client(
            x=0, y=0,
            delivery=delivery,
            pickup=pickup,
            service_duration=int(vt.get("duration", 0) or 0),
            tw_early=lo,
            tw_late=hi,
            prize=_prize(prio),
            required=False,
            name=f"v{i}",
        )

    # --- edges: full matrix per profile. A leg touching the open depot is free. ---
    loc_eng = list(depot_eng) + [vt["location"] for vt in visits]
    locs = m.locations
    for sp, prof in profile_by_speed.items():
        for ai, a in enumerate(locs):
            ea = loc_eng[ai]
            row = None if ea is None else matrix[ea]
            for bi, b in enumerate(locs):
                if ai == bi:
                    continue
                eb = loc_eng[bi]
                dur = 0 if (row is None or eb is None) else int(row[eb] / sp)
                m.add_edge(a, b, distance=dur, duration=dur, profile=prof)

    meta = {
        "num_visits": V,
        "num_vehicles": K,
        "capacity_dims": dims,
        "amount_scale": scale,
        "minimize_vehicles": minimize_vehicles,
        "time_limit_ms": max(1, int(time_limit_ms)),
        "unmodeled": _unmodeled_features(visits, vehicles, multi_tw),
    }

    t0 = time.time()
    res = m.solve(stop=MaxRuntime(max(1, int(time_limit_ms)) / 1000.0), display=False)
    solve_ms = (time.time() - t0) * 1000.0
    best = res.best

    if best is None:
        return {"code": 2, "error": "no solution produced within time limit",
                "solve_ms": round(solve_ms, 1)}, meta

    routes = _routes_from_best(best, num_depots, K)
    repaired = 0
    if not best.is_feasible():
        # PyVRP's best violates a hard constraint (capacity / time window / shift).
        # On instances where feasibility REQUIRES dropping clients — e.g. total demand
        # exceeds total fleet capacity, or shift windows can't cover every visit — the
        # per-visit prize can exceed PyVRP's auto-escalating feasibility-penalty cap, so
        # PyVRP keeps an over-serving *infeasible* solution rather than dropping. Instead
        # of discarding the whole thing (which would report every visit as unserved), we
        # salvage a feasible solution by dropping the minimal set of violating clients
        # per route. Reported via meta.repaired / summary.repaired_drops.
        before = sum(len(r) for r in routes)
        routes = _repair_routes(routes, visits, vehicles, speeds, matrix, dims, allow_overload)
        repaired = before - sum(len(r) for r in routes)

    summary = _metrics_from_routes(routes, visits, vehicles, speeds, matrix)
    summary["code"] = 0
    summary["cost"] = res.cost() if best.is_feasible() else None
    summary["solve_ms"] = round(solve_ms, 1)
    summary["repaired_drops"] = repaired
    meta["repaired"] = repaired > 0
    return summary, meta


def _unmodeled_features(visits, vehicles, multi_tw):
    out = {}
    n_breaks = sum(1 for v in vehicles if v.get("breaks"))
    n_minv = sum(1 for v in vehicles if v.get("minimum_visits"))
    n_vtypes = sum(1 for v in vehicles if v.get("types"))
    n_vttypes = sum(1 for vt in visits if vt.get("types"))
    n_prec = sum(1 for vt in visits if vt.get("precedence") not in (None, "None"))
    n_inv = sum(1 for vt in visits if vt.get("inventory"))
    if n_breaks:
        out["breaks"] = n_breaks
    if n_minv:
        out["minimum_visits"] = n_minv
    if n_vtypes or n_vttypes:
        out["types"] = {"vehicles": n_vtypes, "visits": n_vttypes}
    if n_prec:
        out["precedence"] = n_prec
    if n_inv:
        out["inventory"] = n_inv
    if multi_tw:
        out["multi_time_windows"] = multi_tw
    return out


def _routes_from_best(best, num_depots, K):
    """Per-vehicle ordered visit indices from a PyVRP solution (feasible or not).
    routes[k] = visit indices for vehicle k, empty if unused. PyVRP routes only
    carry served clients; unserved ones never appear."""
    routes = [[] for _ in range(K)]
    for r in best.routes():
        k = r.vehicle_type()  # one type per vehicle => vehicle index
        routes[k] = [idx - num_depots for idx in r.visits()]
    return routes


def _route_violation(perm, v, speed, visits, matrix, dims, allow_overload):
    """First hard-constraint violation on a route, or None if it is feasible.
    Returns ('capacity', dim) | ('tw', position) | ('overtime', None)."""
    if dims and not allow_overload and v.get("capacity") is not None:
        for d in dims:
            capd = _dim_value(v.get("capacity"), d)
            # Load profile: deliveries loaded at the depot (peak at departure), pickups
            # collected en route. Peak load over the route must stay within capacity.
            cur = peak = sum(max(0.0, _dim_value(visits[i].get("demand"), d)) for i in perm)
            for i in perm:
                dem = _dim_value(visits[i].get("demand"), d)
                cur += max(0.0, -dem) - max(0.0, dem)  # pickup adds, delivery unloads
                peak = max(peak, cur)
            if peak > capd + 1e-6:
                return ("capacity", d)
    t = v.get("shift_start_time") or 0
    prev = v.get("start_location")
    for pos, i in enumerate(perm):
        vt = visits[i]
        loc = vt["location"]
        if prev is not None:
            t += int(matrix[prev][loc] / speed)
        lo, hi = _visit_window(vt, None)
        if lo is not None and t < lo:
            t = lo  # wait until the window opens
        if hi is not None and t > hi:
            return ("tw", pos)  # this client is reached after its window closes
        t += int(vt.get("duration", 0) or 0)
        prev = loc
    end = v.get("end_location")
    if prev is not None and end is not None:
        t += int(matrix[prev][end] / speed)
    se = v.get("shift_end_time")
    if se is not None and t > se:
        return ("overtime", None)
    return None


def _repair_routes(routes, visits, vehicles, speeds, matrix, dims, allow_overload):
    """Drop the minimal violating clients per route until every route satisfies its
    hard capacity / time-window / shift constraints. Routes are independent, so each
    is repaired on its own. Deterministic: capacity -> drop the largest-demand client;
    time-window -> drop the late client; overtime -> drop the last client."""
    out = []
    for k, perm in enumerate(routes):
        perm = list(perm)
        v = vehicles[k]
        speed = speeds[k]
        while perm:
            r = _route_violation(perm, v, speed, visits, matrix, dims, allow_overload)
            if r is None:
                break
            kind, info = r
            if kind == "capacity":
                d = info
                j = max(range(len(perm)),
                        key=lambda p: abs(_dim_value(visits[perm[p]].get("demand"), d)))
                perm.pop(j)
            elif kind == "tw":
                perm.pop(info)
            else:  # overtime
                perm.pop()
        out.append(perm)
    return out


def _metrics_from_routes(routes, visits, vehicles, speeds, matrix):
    """Derive quality metrics by simulating each route's timeline. `routes` is the
    per-vehicle list of ordered visit indices (post-repair if the raw best was
    infeasible); unserved visits are those in no route."""
    V = len(visits)
    total_travel = total_service = total_lateness = total_overtime = 0
    routes_used = assigned = 0

    for k, perm in enumerate(routes):
        if not perm:
            continue
        routes_used += 1
        v = vehicles[k]
        speed = speeds[k]
        t = v.get("shift_start_time") or 0
        prev_loc = v.get("start_location")
        for vi in perm:
            assigned += 1
            vt = visits[vi]
            loc = vt["location"]
            if prev_loc is not None:
                total_travel += int(matrix[prev_loc][loc] / speed)
                t += int(matrix[prev_loc][loc] / speed)
            lo, hi = _visit_window(vt, None)
            if lo is not None and t < lo:
                t = lo  # wait until the window opens
            if hi is not None and t > hi:
                total_lateness += t - hi
            svc = int(vt.get("duration", 0) or 0)
            total_service += svc
            t += svc
            prev_loc = loc
        end_loc = v.get("end_location")
        if prev_loc is not None and end_loc is not None:
            total_travel += int(matrix[prev_loc][end_loc] / speed)
            t += int(matrix[prev_loc][end_loc] / speed)
        se = v.get("shift_end_time")
        if se is not None and t > se:
            total_overtime += t - se

    dropped = [i for i in range(V) if i not in {x for perm in routes for x in perm}]
    return {
        "routes": routes_used,
        "assigned": assigned,
        "unassigned": V - assigned,
        "duration": total_travel,    # total travel time (s); ~ VROOM summary.duration
        "service": total_service,
        "lateness": total_lateness,
        "overtime": total_overtime,
        "vehicle_routes": routes,    # Vec<Vec<visit_index>>, per vehicle in order
        "dropped": dropped,          # unassigned visit indices
    }


def default_time_limit_ms(n_visits):
    """Size-scaled fallback budget in milliseconds. Only used when no explicit
    budget is given; the benchmark normally passes the engine's recorded
    per-problem runtime (see --reference-benchmark in the Rust runner)."""
    return int(min(30, max(1, math.ceil(n_visits * 0.1)))) * 1000


def summary_line(name, summary, meta):
    if summary["code"] != 0:
        return f"{name}: code={summary['code']} {summary.get('error','')}"
    s = summary
    warn = f" unmodeled={list(meta['unmodeled'])}" if meta["unmodeled"] else ""
    if s.get("repaired_drops"):
        warn += f" repaired_drops={s['repaired_drops']}"
    return (f"{name}: routes={s['routes']} assigned={s['assigned']}/{meta['num_visits']} "
            f"unassigned={s['unassigned']} duration={s['duration']} service={s['service']} "
            f"lateness={s['lateness']} overtime={s['overtime']} cost={s['cost']} "
            f"solve_ms={s['solve_ms']}{warn}")


# ---------------------------------------------------------------------------
# CLI: single instance + batch
# ---------------------------------------------------------------------------
def run_single(args):
    with open(args.instance) as f:
        instance = json.load(f)
    tl_ms = (args.time_limit * 1000) if args.time_limit else default_time_limit_ms(len(instance["visits"]))
    summary, meta = build_and_solve(instance, tl_ms)
    name = os.path.basename(args.instance)
    print(summary_line(name, summary, meta))
    if args.out:
        json.dump({"summary": summary, "meta": meta}, open(args.out, "w"), indent=2)
    return 0 if summary["code"] == 0 else summary["code"]


def run_batch(args):
    files = sorted(glob.glob(os.path.join(args.cache, "instance-*.json")))[: args.n]
    solved = errored = 0
    total_visits = total_unassigned = 0
    solve_times = []
    rows = []
    n_unmodeled = 0
    for f in files:
        name = os.path.basename(f)
        try:
            instance = json.load(open(f))
            tl_ms = (args.time_limit * 1000) if args.time_limit else default_time_limit_ms(len(instance["visits"]))
            summary, meta = build_and_solve(instance, tl_ms)
        except Exception as e:  # noqa: BLE001 - batch keeps going
            errored += 1
            rows.append((name, "error", str(e)[:80]))
            continue
        if summary["code"] == 0:
            solved += 1
            total_visits += meta["num_visits"]
            total_unassigned += summary["unassigned"]
            solve_times.append(summary["solve_ms"])
            if meta["unmodeled"]:
                n_unmodeled += 1
            rows.append((name, "solved", summary))
        else:
            errored += 1
            rows.append((name, "no_solution", summary.get("error", "")))

    n = len(files)
    print(f"\n=== PyVRP batch over {n} instances ===")
    print(f"  solved        : {solved}")
    print(f"  errored       : {errored}")
    print(f"  with unmodeled: {n_unmodeled} (features ignored — see meta.unmodeled)")
    if solve_times:
        st = sorted(solve_times)
        print(f"  solve time : avg={sum(st)/len(st):.0f}ms  "
              f"p50={st[len(st)//2]:.0f}ms  max={st[-1]:.0f}ms")
        print(f"  visits total={total_visits}  unassigned={total_unassigned} "
              f"({100*total_unassigned/max(1,total_visits):.2f}%)")
    if errored:
        print("\n  errors / no-solution:")
        for r in rows:
            if r[1] in ("error", "no_solution"):
                print(f"    {r[0]}: {r[1]} {r[2]}")
    if args.csv:
        import csv
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["instance", "status", "routes", "assigned", "unassigned",
                        "duration", "service", "lateness", "overtime", "cost", "solve_ms"])
            for name, status, payload in rows:
                if status == "solved":
                    s = payload
                    w.writerow([name, status, s["routes"], s["assigned"], s["unassigned"],
                                s["duration"], s["service"], s["lateness"], s["overtime"],
                                s["cost"], s["solve_ms"]])
                else:
                    w.writerow([name, status, "", "", "", "", "", "", "", "", ""])
        print(f"\n  wrote {args.csv}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance", nargs="?", help="path to a cached instance JSON")
    ap.add_argument("-o", "--out", help="write {summary, meta} JSON here")
    ap.add_argument("--time-limit", type=int,
                    help="per-instance solve budget in seconds (default: size-scaled)")
    ap.add_argument("--batch", action="store_true", help="solve a sample from --cache")
    ap.add_argument("--cache", default="/cache", help="instance cache dir (batch mode)")
    ap.add_argument("--n", type=int, default=150, help="instances to solve (batch mode)")
    ap.add_argument("--csv", help="write per-instance batch results here")
    args = ap.parse_args()

    if args.batch:
        run_batch(args)
        return 0
    if not args.instance:
        ap.error("provide an instance path, or --batch")
    return run_single(args)


if __name__ == "__main__":
    sys.exit(main())
