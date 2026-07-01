#!/usr/bin/env python3
"""Compare solver results/ into a per-metric table + a win-rate table (+ runtime).

Reads results/<solver>/<instance>.json, recomputes metrics from each
(instance, solution) pair, and prints/writes the comparison. No composite score.

  python3 analysis/analyze.py                     # the 4 competitors
  python3 analysis/analyze.py --include-provisional   # also show routific-* (provisional)
"""
from __future__ import annotations
import argparse
import csv
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

# (key, label, needs_multiroute) — every metric here is lower-is-better.
METRICS = [
    ("travel_time", "Total travel time (s)", False),
    ("num_vehicles", "Number of vehicles", False),
    ("inter_route_crossings_sum", "Crossings between routes (sum)", True),
    ("inter_route_crossings_max", "Crossings between routes (max)", True),
    ("intra_route_crossings", "Crossings within a route", False),
    ("workload_imbalance", "Workload imbalance", True),
    ("route_duration_variance", "Route-duration variance", True),
    ("idle_time", "Idle / wait time (s)", False),
]


def load_instance(name: str) -> dict:
    with gzip.open(glob.glob(os.path.join(DATASET, "*", f"{name}.json.gz"))[0], "rb") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-provisional", action="store_true",
                    help="include routific-* result sets (flagged provisional / not comparable)")
    args = ap.parse_args()

    solvers = sorted(d for d in os.listdir(RESULTS)
                     if os.path.isdir(os.path.join(RESULTS, d))
                     and not d.startswith("_")
                     and (args.include_provisional or not d.startswith("routific")))
    if not solvers:
        sys.exit("no solver result dirs under results/")

    have = {s: {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(RESULTS, s, "*.json"))} for s in solvers}
    instances = sorted(set.intersection(*have.values()))
    if not instances:
        sys.exit("no instances common to all selected solvers")

    inst_cache: dict[str, dict] = {}
    data: dict[tuple[str, str], dict] = {}
    multiroute: set[str] = set()
    for s in solvers:
        for name in instances:
            inst = inst_cache.setdefault(name, load_instance(name))
            sol = json.load(open(os.path.join(RESULTS, s, f"{name}.json")))
            m = compute(inst, sol)
            data[(s, name)] = m
            if m["num_vehicles"] >= 2:
                multiroute.add(name)

    w = 15
    print(f"solvers: {solvers}")
    print(f"instances ({len(instances)}): {instances}")
    print(f"multi-route instances ({len(multiroute)}): {sorted(multiroute)}\n")

    # --- per-metric means (lower is better) ---
    print("=== Per-metric mean (lower is better) ===")
    print("Metric".ljust(34) + "".join(s.ljust(w) for s in solvers))
    comp_rows = []
    for key, label, needs_mr in METRICS:
        insts = [n for n in instances if (not needs_mr or n in multiroute)]
        row = {"metric": label, "n": len(insts)}
        line = label.ljust(34)
        for s in solvers:
            vals = [data[(s, n)][key] for n in insts if data[(s, n)][key] is not None]
            mv = statistics.mean(vals) if vals else float("nan")
            row[s] = round(mv, 2)
            line += f"{mv:,.2f}".ljust(w)
        print(line)
        comp_rows.append(row)

    # Runtime is intentionally NOT compared here: the solvers ran under different clocks and
    # stopping rules (fixed effort vs a flat budget vs an iteration cap), so it isn't a fair speed
    # comparison. It returns once there's a single clock + a per-problem budget tied to a valid
    # Routific run. See analysis/README.md.

    # --- win rate (% of applicable instances where the solver is best; ties count for each) ---
    print("\n=== Win rate (% of applicable instances where solver is best) ===")
    print("Best on...".ljust(34) + "".join(s.ljust(w) for s in solvers))
    win_rows = []
    for key, label, needs_mr in METRICS:
        insts = [n for n in instances if (not needs_mr or n in multiroute)]
        wins = {s: 0 for s in solvers}
        for n in insts:
            vals = {s: data[(s, n)][key] for s in solvers if data[(s, n)][key] is not None}
            if not vals:
                continue
            best = min(vals.values())
            for s, v in vals.items():
                if v == best:
                    wins[s] += 1
        row = {"metric": label, "n": len(insts)}
        line = f"Fewest {label}".ljust(34) if "Crossings" in label else f"Lowest {label}".ljust(34)
        for s in solvers:
            pct = (100 * wins[s] / len(insts)) if insts else 0
            row[s] = round(pct)
            line += f"{pct:.0f}%".ljust(w)
        print(line)
        win_rows.append(row)

    # --- write CSVs ---
    outdir = os.path.join(RESULTS, "_analysis")
    os.makedirs(outdir, exist_ok=True)
    for fname, rows in [("comparison.csv", comp_rows), ("win_rate.csv", win_rows)]:
        with open(os.path.join(outdir, fname), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    print(f"\nwrote results/_analysis/{{comparison,win_rate}}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
