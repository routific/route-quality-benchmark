#!/usr/bin/env python3
"""Solve a cached benchmark instance (engine `InstanceWrapper` JSON) with Google
OR-Tools, reusing the engine's own travel-time matrix so the two solvers see the
*same* problem (same travel times, shifts, time windows, capacities) and can be
compared apples-to-apples. No OSRM/routing backend is involved.

The OR-Tools model can represent the engine's soft constraints, but the benchmark
crate zeroes every soft-constraint allowance before solving so that all solvers
face the *same* hard-constrained problem (a fair cross-solver comparison). The
soft paths below therefore engage only when an allowance is non-zero — e.g. a
local `--soft-override` run, not the benchmark default:

  etas_options.max_visit_lateness  > 0  -> soft visit time-window upper bound
  etas_options.max_vehicle_overtime> 0  -> soft route-end (overtime) upper bound
  etas_options.allow_capacity_overload  -> capacity dimension made non-binding
  visit.priority                        -> disjunction with drop penalty (always)

Mapping (engine -> OR-Tools)
  distances[i][j]        -> arc transit (cost = travel time); /speed per vehicle
  vehicle.speed          -> per-vehicle transit scaling (time = matrix / speed)
  vehicle.start/end_loc  -> per-vehicle start/end node (null => 0-cost open end)
  vehicle.shift_*_time   -> Time dimension start min / end max (hard or soft)
  vehicle.strict_start   -> start cumul fixed to shift_start_time
  vehicle.capacity       -> capacity dimension upper bound (per typed dimension)
  visit.location         -> node -> location index
  visit.duration         -> service time (added to Time transit on leaving)
  visit.time_windows     -> Time cumul [start, end] (hard) or soft upper bound
  visit.demand           -> capacity dimension demand (signed; +delivery/-pickup)
  visit.priority         -> AddDisjunction penalty = priority * BIG (lexicographic)
  secondary_objective.minimize_vehicles -> SetFixedCostOfAllVehicles (fleet
                            minimization; objective stays serve > vehicles > distance)

NOT modeled (reported in meta.unmodeled, still solved): breaks, minimum_visits,
vehicle/visit types (skills), inventory, precedence/pickup-delivery pairs,
multiple disjoint time windows per visit (relaxed to their enclosing span).

The engine's exact penalty *weights* live in an external crate, so absolute cost
is not comparable across solvers. Compare quality metrics instead: unassigned
(weighted by priority), travel time, vehicles used, lateness, overtime.

Exit codes: 0 = solved, 1 = error, 2 = no solution found within the time limit.
"""
import argparse
import glob
import json
import math
import os
import sys
import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# The engine's "soft" sentinel for max_visit_lateness / max_vehicle_overtime
# (30 days). The benchmark crate now zeroes these for a fair comparison, so this
# only applies to local --soft-override runs (see apply_soft_override).
OVERTIME_LATENESS_SOFT_MAX = 60 * 60 * 24 * 30

# 10 years of slack past the latest real timestamp; upper bound for open shifts /
# half-open windows. Stays well under int64 for our ~1.7e9 timestamps.
HORIZON_SLACK = 10 * 365 * 24 * 3600

# Dropping a visit must dominate any routing cost so "minimize unassigned
# (weighted by priority)" is lexicographically primary, as in the engine. Travel
# costs are seconds (<~1e7 total per instance), so 1e9 per priority unit is safe
# and priority*BIG stays far below int64 max.
DROP_PENALTY_UNIT = 1_000_000_000

# Fixed cost per vehicle *used*, applied only when the instance's objective is to
# minimize the fleet (secondary_objective.minimize_vehicles). Sits between routing
# cost and the drop penalty so the objective is serve(prize) > vehicles > distance:
# >> total travel (<~1e7 s) so reducing the fleet beats any distance increase, yet
# < DROP_PENALTY_UNIT (1e9) so serving a visit still beats dropping it. Env-tunable.
VEHICLE_FIXED_COST = int(os.environ.get("ORTOOLS_FIXED_COST", "100000000"))

# Cost per second of lateness / overtime. 1:1 with travel-time seconds — a
# deliberate, documented choice (real engine weights are not available here).
LATENESS_COEF = 1
OVERTIME_COEF = 1


# ---------------------------------------------------------------------------
# instance -> OR-Tools model helpers
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
    fractional demands/capacities survive the cast to OR-Tools ints."""
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


def apply_soft_override(instance):
    """Local what-if helper: for non-minimize_vehicles instances, turn the
    engine's soft constraints ON. NOTE: the benchmark crate now zeroes soft
    constraints for a fair cross-solver comparison, so this no longer mirrors
    `set_problem_configs`; it's only for exploring soft-constrained behavior via
    `--soft-override` (the benchmark path never sets it)."""
    so = instance.get("secondary_objective") or {}
    if so.get("minimize_vehicles"):
        return
    etas = instance.setdefault("etas_options", {})
    etas["max_visit_lateness"] = OVERTIME_LATENESS_SOFT_MAX
    etas["max_vehicle_overtime"] = OVERTIME_LATENESS_SOFT_MAX
    etas["allow_capacity_overload"] = True


def build_and_solve(instance, time_limit_ms, log=lambda *_: None):
    """Build the OR-Tools model for a *prepared* instance and solve it. Returns
    (summary_dict, meta_dict). summary['code'] is 0 solved / 2 no-solution."""
    visits = instance["visits"]
    vehicles = instance["vehicles"]
    matrix = instance["distances"]
    if not isinstance(matrix, list) or (matrix and not isinstance(matrix[0], list)):
        raise ValueError("distances is not a dense NxN matrix (sparse not supported)")
    etas = instance.get("etas_options") or {}
    max_lateness = etas.get("max_visit_lateness", 0) or 0
    max_overtime = etas.get("max_vehicle_overtime", 0) or 0
    allow_overload = bool(etas.get("allow_capacity_overload"))
    minimize_vehicles = bool((instance.get("secondary_objective") or {}).get("minimize_vehicles"))

    V = len(visits)
    K = len(vehicles)
    horizon = _horizon(visits, vehicles)

    # Node layout: 0..V-1 visits, then a (start, end) node pair per vehicle.
    starts = [V + 2 * k for k in range(K)]
    ends = [V + 2 * k + 1 for k in range(K)]
    n_nodes = V + 2 * K

    node_loc = [None] * n_nodes      # location index, or None for an open depot
    node_service = [0] * n_nodes
    for i, vt in enumerate(visits):
        node_loc[i] = vt["location"]
        node_service[i] = int(vt.get("duration", 0) or 0)
    for k, v in enumerate(vehicles):
        node_loc[starts[k]] = v.get("start_location")   # None => open start
        node_loc[ends[k]] = v.get("end_location")       # None => open end

    manager = pywrapcp.RoutingIndexManager(n_nodes, K, starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def travel(f_node, t_node, speed):
        lf, lt = node_loc[f_node], node_loc[t_node]
        if lf is None or lt is None:    # arc to/from an open depot is free
            return 0
        return int(matrix[lf][lt] / speed)

    # Dedupe transit callbacks by speed (most instances are all speed 1.0).
    speeds = [round(float(v.get("speed", 1.0) or 1.0), 4) for v in vehicles]
    cost_cb_by_speed, time_cb_by_speed = {}, {}
    for sp in set(speeds):
        def make_cost(speed):
            def cb(fi, ti):
                return travel(manager.IndexToNode(fi), manager.IndexToNode(ti), speed)
            return cb

        def make_time(speed):
            def cb(fi, ti):
                f = manager.IndexToNode(fi)
                return travel(f, manager.IndexToNode(ti), speed) + node_service[f]
            return cb

        cost_cb_by_speed[sp] = routing.RegisterTransitCallback(make_cost(sp))
        time_cb_by_speed[sp] = routing.RegisterTransitCallback(make_time(sp))

    for k in range(K):
        routing.SetArcCostEvaluatorOfVehicle(cost_cb_by_speed[speeds[k]], k)

    # --- Time dimension (travel + service), per-vehicle transit ---
    routing.AddDimensionWithVehicleTransits(
        [time_cb_by_speed[speeds[k]] for k in range(K)],
        horizon,          # slack (waiting) allowed
        horizon,          # max cumul
        False,            # don't fix start cumul to zero (we use absolute time)
        "Time",
    )
    time_dim = routing.GetDimensionOrDie("Time")

    for k, v in enumerate(vehicles):
        s_idx, e_idx = routing.Start(k), routing.End(k)
        ss, se = v.get("shift_start_time"), v.get("shift_end_time")
        if ss is not None:
            if v.get("strict_start"):
                time_dim.CumulVar(s_idx).SetRange(ss, ss)
            else:
                time_dim.CumulVar(s_idx).SetMin(ss)
        if se is not None:
            if max_overtime > 0:
                time_dim.CumulVar(e_idx).SetMax(se + max_overtime)
                time_dim.SetCumulVarSoftUpperBound(e_idx, se, OVERTIME_COEF)
            else:
                time_dim.CumulVar(e_idx).SetMax(se)

    multi_tw = 0
    for i, vt in enumerate(visits):
        idx = manager.NodeToIndex(i)
        tws = vt.get("time_windows") or []
        if tws:
            if len(tws) > 1:
                multi_tw += 1
            lo = min((tw["start"] for tw in tws if tw.get("start") is not None), default=0)
            hi = max((tw["end"] for tw in tws if tw.get("end") is not None), default=horizon)
            time_dim.CumulVar(idx).SetMin(lo)
            if max_lateness > 0:
                time_dim.CumulVar(idx).SetMax(hi + max_lateness)
                time_dim.SetCumulVarSoftUpperBound(idx, hi, LATENESS_COEF)
            else:
                time_dim.CumulVar(idx).SetMax(hi)

    # --- Capacity dimensions (one per typed dimension, or one scalar) ---
    dims = _load_dims(vehicles)
    scale = 1
    n_pickup = 0
    if dims is not None:
        vals = []
        for v in vehicles:
            for d in dims:
                vals.append(_dim_value(v.get("capacity"), d))
        for vt in visits:
            for d in dims:
                vals.append(abs(_dim_value(vt.get("demand"), d)))
        scale = _pick_scale(vals)
        total_demand = sum(
            abs(_dim_value(vt.get("demand"), d)) for vt in visits for d in dims
        )
        big_cap = int(total_demand * scale) + 1   # non-binding cap

        for d in dims:
            demands = [0] * n_nodes
            for i, vt in enumerate(visits):
                val = int(round(_dim_value(vt.get("demand"), d) * scale))
                if val < 0:
                    n_pickup += 1
                demands[i] = val
            cb = routing.RegisterUnaryTransitCallback(
                lambda fi, _dm=demands: _dm[manager.IndexToNode(fi)]
            )
            caps = []
            for v in vehicles:
                cap = v.get("capacity")
                if cap is None or allow_overload:
                    caps.append(big_cap)
                else:
                    caps.append(int(round(_dim_value(cap, d) * scale)))
            routing.AddDimensionWithVehicleCapacity(
                cb, 0, caps, True, f"cap[{d}]"
            )

    # --- Droppable visits: penalty = priority * BIG (lexicographic primary) ---
    for i, vt in enumerate(visits):
        prio = int(round(vt.get("priority", 1) or 0))
        routing.AddDisjunction([manager.NodeToIndex(i)], prio * DROP_PENALTY_UNIT)

    # --- Minimize the fleet: a fixed cost per vehicle used, only when the
    #     instance's objective is to minimize vehicles. Hard constraints stay hard;
    #     this just adds serve > vehicles > distance to the objective. ---
    if minimize_vehicles:
        routing.SetFixedCostOfAllVehicles(VEHICLE_FIXED_COST)

    # --- Search params ---
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    # Millisecond precision so the budget can match the engine's recorded
    # per-problem wall-clock exactly (which can be sub-second on small problems).
    params.time_limit.FromMilliseconds(max(1, int(time_limit_ms)))

    unmodeled = _unmodeled_features(visits, vehicles, multi_tw, n_pickup)
    meta = {
        "num_visits": V,
        "num_vehicles": K,
        "capacity_dims": dims,
        "amount_scale": scale,
        "minimize_vehicles": minimize_vehicles,
        "soft": {
            "max_visit_lateness": max_lateness,
            "max_vehicle_overtime": max_overtime,
            "allow_capacity_overload": allow_overload,
        },
        "time_limit_ms": max(1, int(time_limit_ms)),
        "unmodeled": unmodeled,
    }

    t0 = time.time()
    solution = routing.SolveWithParameters(params)
    solve_ms = (time.time() - t0) * 1000.0

    if solution is None:
        return {"code": 2, "error": "no solution within time limit",
                "solve_ms": round(solve_ms, 1)}, meta

    summary = _extract(routing, manager, solution, time_dim, visits, vehicles,
                       node_loc, node_service, speeds, matrix, max_lateness)
    summary["code"] = 0
    summary["cost"] = solution.ObjectiveValue()
    summary["solve_ms"] = round(solve_ms, 1)
    return summary, meta


def _unmodeled_features(visits, vehicles, multi_tw, n_pickup):
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
    if n_pickup:
        out["pickups_negative_demand"] = n_pickup
    return out


def _extract(routing, manager, solution, time_dim, visits, vehicles,
             node_loc, node_service, speeds, matrix, max_lateness):
    V = len(visits)
    routes_used = 0
    total_travel = 0
    total_service = 0
    total_lateness = 0
    total_overtime = 0
    assigned = 0
    # Per-vehicle ordered visit indices (one list per vehicle, in instance order,
    # empty if the vehicle is unused). This is what the Rust benchmark solver maps
    # back into a vrp_modeling::Solution.
    routes = []

    for k, v in enumerate(vehicles):
        index = routing.Start(k)
        route_perm = []
        route_travel = 0
        speed = speeds[k]
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            nxt = solution.Value(routing.NextVar(index))
            nnode = manager.IndexToNode(nxt)
            lf, lt = node_loc[node], node_loc[nnode]
            if lf is not None and lt is not None:
                route_travel += int(matrix[lf][lt] / speed)
            if node < V:
                route_perm.append(node)
                assigned += 1
                total_service += node_service[node]
                arr = solution.Value(time_dim.CumulVar(index))
                tws = visits[node].get("time_windows") or []
                if tws:
                    hi = max((tw["end"] for tw in tws if tw.get("end") is not None),
                             default=None)
                    if hi is not None and arr > hi:
                        total_lateness += arr - hi
            index = nxt
        routes.append(route_perm)
        if route_perm:
            routes_used += 1
            total_travel += route_travel
            se = v.get("shift_end_time")
            end_time = solution.Value(time_dim.CumulVar(routing.End(k)))
            if se is not None and end_time > se:
                total_overtime += end_time - se

    assigned_set = {n for perm in routes for n in perm}
    dropped = [i for i in range(V) if i not in assigned_set]

    return {
        "routes": routes_used,
        "assigned": assigned,
        "unassigned": V - assigned,
        "duration": total_travel,      # total travel time (s); ~ VROOM summary.duration
        "service": total_service,
        "lateness": total_lateness,
        "overtime": total_overtime,
        # Assignment detail for the benchmark integration (ignored by the CLI):
        "vehicle_routes": routes,      # Vec<Vec<visit_index>>, per vehicle in order
        "dropped": dropped,            # unassigned visit indices
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
    flags = "+soft" if any(meta["soft"].values()) else ""
    warn = f" unmodeled={list(meta['unmodeled'])}" if meta["unmodeled"] else ""
    return (f"{name}: routes={s['routes']} assigned={s['assigned']}/{meta['num_visits']} "
            f"unassigned={s['unassigned']} duration={s['duration']} service={s['service']} "
            f"lateness={s['lateness']} overtime={s['overtime']} cost={s['cost']} "
            f"solve_ms={s['solve_ms']} {flags}{warn}")


# ---------------------------------------------------------------------------
# CLI: single instance + batch
# ---------------------------------------------------------------------------
def run_single(args):
    with open(args.instance) as f:
        instance = json.load(f)
    if args.soft_override:
        apply_soft_override(instance)
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
            if args.soft_override:
                apply_soft_override(instance)
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
    print(f"\n=== OR-Tools batch over {n} instances ===")
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
    ap.add_argument("--soft-override", action="store_true",
                    help="replicate benchmark set_problem_configs (force soft constraints on)")
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
