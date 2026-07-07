#!/usr/bin/env python3
"""Coverage-gated fair comparison — the method behind docs/results.md.

Solver quality is only comparable when the solvers serve the same work, and travel
time is only comparable when they also use the same number of vehicles (more stops
or more trucks mechanically means more travel). So this runs in three gated stages:

  Stage 1  coverage — number of unserved stops (the primary axis)
  Stage 2  every other metric, ONLY on instances where all solvers serve the SAME count
  Stage 3  travel time — pairwise vs a reference solver, ONLY where the pair also
           uses the SAME number of vehicles

Every metric is recomputed from the (instance, solution) pair by compute_metrics, so
the numbers are reproducible from the published result files alone.

  python3 analysis/fair_compare.py                       # all solver dirs under results/
  python3 analysis/fair_compare.py --exclude jsprit      # drop a solver (bigger common set)
  python3 analysis/fair_compare.py --reference routific   # travel is compared vs this solver
"""
from __future__ import annotations
import argparse
import glob
import gzip
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_metrics import compute  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(REPO, "datasets", "public-benchmark")
RESULTS = os.path.join(REPO, "results")

# (key, label, multiroute-only) — everything lower-is-better.
QUALITY = [
    ("num_vehicles", "Number of vehicles", False),
    ("inter_route_crossings_sum", "Crossings between routes (sum)", True),
    ("inter_route_crossings_max", "Crossings between routes (max)", True),
    ("intra_route_crossings", "Crossings within a route", False),
    ("workload_imbalance", "Workload imbalance", True),
    ("route_duration_variance", "Route-duration variance", True),
    ("idle_time", "Idle / wait (s)", False),
]


def load_instance(name: str) -> dict:
    with gzip.open(glob.glob(os.path.join(DATASET, "*", f"{name}.json.gz"))[0], "rb") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exclude", default="", help="comma-separated solver dirs to skip, e.g. jsprit")
    ap.add_argument("--reference", default="routific", help="solver to compare travel time against")
    ap.add_argument("--only-min-vehicles", action="store_true",
                    help="restrict to instances with minimize_vehicles=True")
    args = ap.parse_args()
    exclude = {s for s in args.exclude.split(",") if s}

    solvers = sorted(d for d in os.listdir(RESULTS)
                     if os.path.isdir(os.path.join(RESULTS, d))
                     and not d.startswith("_") and not d.startswith("routific-")
                     and d not in exclude)
    if len(solvers) < 2:
        sys.exit("need >= 2 solver result dirs under results/")
    ref = args.reference if args.reference in solvers else solvers[0]

    have = {s: {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(RESULTS, s, "*.json"))} for s in solvers}
    common = sorted(set.intersection(*have.values()))
    if not common:
        sys.exit("no instances common to all selected solvers")

    M, inst_cache = {}, {}
    for n in common:
        inst = inst_cache[n] = load_instance(n)
        for s in solvers:
            M[(s, n)] = compute(inst, json.load(open(os.path.join(RESULTS, s, f"{n}.json"))))
    if args.only_min_vehicles:
        common = [n for n in common if inst_cache[n].get("minimize_vehicles")]
        if not common:
            sys.exit("no minimize_vehicles=True instances in the common set")

    def mean(xs): return statistics.mean(xs) if xs else float("nan")

    def wins(names, key):
        w = {s: 0 for s in solvers}
        for n in names:
            best = min(M[(s, n)][key] for s in solvers)
            for s in solvers:
                if M[(s, n)][key] == best:
                    w[s] += 1
        return {s: round(100 * w[s] / len(names)) if names else 0 for s in w}

    print(f"solvers: {solvers}   reference: {ref}")
    print(f"common instances: {len(common)}\n")

    # ---- Stage 1: coverage ----
    print("=" * 68 + "\nSTAGE 1 — COVERAGE (unserved), full common set\n" + "=" * 68)
    print("metric".ljust(16) + "".join(s.rjust(12) for s in solvers))
    print("mean unserved".ljust(16) + "".join(f"{mean([M[(s,n)]['num_unserved'] for n in common]):>12.2f}" for s in solvers))
    wr = wins(common, "num_unserved")
    print("fewest-uns %".ljust(16) + "".join(f"{str(wr[s])+'%':>12}" for s in solvers))
    eq = [n for n in common if len({M[(s, n)]["num_unserved"] for s in solvers}) == 1]
    mr = [n for n in eq if max(M[(s, n)]["num_vehicles"] for s in solvers) >= 2]
    print(f"\n-> EQUAL-unserved across all solvers: {len(eq)} instances ({len(mr)} multi-route)")

    # ---- Stage 2: quality at equal coverage ----
    print("\n" + "=" * 68 + f"\nSTAGE 2 — quality at EQUAL coverage ({len(eq)} instances)\n" + "=" * 68)
    print("metric (mean)".ljust(32) + "".join(s.rjust(12) for s in solvers) + "   n")
    for key, label, mronly in QUALITY:
        ns = mr if mronly else eq
        print(label.ljust(32) + "".join(f"{mean([M[(s,n)][key] for n in ns]):>12,.1f}" for s in solvers) + f"  {len(ns):>4}")
    print("\n" + "win rate (%)".ljust(32) + "".join(s.rjust(12) for s in solvers))
    for key, label, mronly in QUALITY:
        ns = mr if mronly else eq
        wr = wins(ns, key)
        print(label.ljust(32) + "".join(f"{str(wr[s])+'%':>12}" for s in solvers))

    # ---- Stage 3: travel at equal coverage AND equal vehicles ----
    print("\n" + "=" * 68 + f"\nSTAGE 3 — TRAVEL, {ref} vs each, EQUAL unserved AND EQUAL # vehicles\n" + "=" * 68)
    for s in solvers:
        if s == ref:
            continue
        sub = [n for n in common if M[(ref, n)]["num_unserved"] == M[(s, n)]["num_unserved"]
               and M[(ref, n)]["num_vehicles"] == M[(s, n)]["num_vehicles"]]
        if not sub:
            print(f"  {ref} vs {s}: no equal-coverage-equal-fleet instances")
            continue
        tr, tf = mean([M[(ref, n)]["travel_time"] for n in sub]), mean([M[(s, n)]["travel_time"] for n in sub])
        low = sum(1 for n in sub if M[(ref, n)]["travel_time"] < M[(s, n)]["travel_time"])
        print(f"  {ref} vs {s:<9} (n={len(sub):3d}):  travel {tr:>9,.0f} / {tf:>9,.0f}  "
              f"ratio {tr/tf:4.2f}   {ref} lower on {low}/{len(sub)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
