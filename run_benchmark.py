#!/usr/bin/env python3
"""Batch runner: solve a set of Standard Instances with each solver -> results/.

For each selected solver it brings the Docker service up, solves the given
instances (each solver's run.py writes results/<solver>/<instance>.json), then
tears the service down. jsprit auto-skips instances >400 stops.

  python3 run_benchmark.py                                  # 5-instance sample, all solvers
  python3 run_benchmark.py --solvers vroom,pyvrp
  python3 run_benchmark.py --instances pb-0187,pb-0013 --keep-up
  python3 run_benchmark.py --sample 20 --time-limit-ms 5000
"""
from __future__ import annotations
import argparse
import csv
import glob
import gzip
import json
import os
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(REPO, "datasets", "public-benchmark")

SOLVERS = {
    "vroom":   {"port": 3030, "build": False},
    "pyvrp":   {"port": 5002, "build": True},
    "ortools": {"port": 5001, "build": True},
    "jsprit":  {"port": 8080, "build": True},
}
# Default sample: one per VRP type, all <=400 stops (so jsprit runs too).
DEFAULT_INSTANCES = ["pb-0187", "pb-0013", "pb-0064", "pb-0149", "pb-0164"]


def find_instance(name: str) -> str:
    hits = glob.glob(os.path.join(DATASET, "*", f"{name}.json.gz"))
    if not hits:
        sys.exit(f"instance not found in {DATASET}: {name}")
    return hits[0]


def wait_ready(solver: str, port: int, tries: int = 60) -> bool:
    url = f"http://localhost:{port}"
    for _ in range(tries):
        try:
            if solver == "vroom":  # VROOM has no GET health; probe with a trivial solve
                data = (b'{"vehicles":[{"id":0,"start_index":0}],"jobs":[{"id":0,'
                        b'"location_index":0}],"matrices":{"car":{"durations":[[0]]}}}')
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=3).read()
            else:
                urllib.request.urlopen(url + ("/health" if solver == "jsprit" else "/"), timeout=3).read()
            return True
        except Exception:
            time.sleep(1)
    return False


def compose(solver: str, *args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=os.path.join(REPO, "solvers", solver),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solvers", default="vroom,pyvrp,ortools,jsprit")
    ap.add_argument("--instances", help="comma-separated instance names (default: 5-instance sample)")
    ap.add_argument("--sample", type=int, help="use the first N dataset instances instead of the default")
    ap.add_argument("--time-limit-ms", type=int, help="flat solve budget for pyvrp/ortools/jsprit")
    ap.add_argument("--budget-from-routific", action="store_true",
                    help="per-problem budget = max(2000, 2 x Routific's runtime) read from the "
                         "results/routific/ files — the rule for building budgets from a Routific column")
    ap.add_argument("--budget-map", help="TSV (pb_name/budget_ms) explicit per-problem budget; the official "
                                         "run uses results/competitor-budgets.tsv")
    ap.add_argument("--max-stops", type=int, help="skip instances with more than this many visits (all solvers)")
    ap.add_argument("--keep-up", action="store_true", help="leave services running afterwards")
    args = ap.parse_args()

    # Per-problem competitor budget. The official run uses --budget-map results/competitor-budgets.tsv:
    # the budgets the published PyVRP/OR-Tools columns ran at, max(2s, 2 x the current Routific runtime on
    # that problem), except pb-0089/pb-0102 (July solutions, 2 x the July runtime). --budget-from-routific
    # applies the rule to the runtimes in results/routific/<name>.json (i.e. the current Routific column).
    budgets = {}
    if args.budget_from_routific:
        for f in glob.glob(os.path.join(REPO, "results", "routific", "*.json")):
            rt = json.load(open(f)).get("runtime_ms") or 0
            budgets[os.path.basename(f)[:-5]] = max(2000, 2 * int(rt))
    elif args.budget_map:
        budgets = {r["pb_name"]: int(r["budget_ms"]) for r in csv.DictReader(open(args.budget_map), delimiter="\t")}

    solvers = [s for s in args.solvers.split(",") if s in SOLVERS]
    if args.instances:
        names = args.instances.split(",")
    elif args.sample:
        files = sorted(glob.glob(os.path.join(DATASET, "*", "*.json.gz")))[: args.sample]
        names = [os.path.basename(f).split(".")[0] for f in files]
    else:
        names = DEFAULT_INSTANCES
    instances = [(n, find_instance(n)) for n in names]

    if args.max_stops:
        keep = []
        for n, p in instances:
            with gzip.open(p, "rb") as f:
                if len(json.load(f)["visits"]) <= args.max_stops:
                    keep.append((n, p))
        print(f"size cap {args.max_stops}: kept {len(keep)}/{len(instances)} instances")
        instances = keep

    print(f"solvers: {solvers}\ninstances ({len(instances)}): {[n for n, _ in instances]}")
    for solver in solvers:
        cfg = SOLVERS[solver]
        print(f"\n=== {solver}: bringing service up ===")
        compose(solver, "up", "-d", *(["--build"] if cfg["build"] else []))
        if not wait_ready(solver, cfg["port"]):
            print(f"  {solver}: NOT READY — skipping")
            if not args.keep_up:
                compose(solver, "down")
            continue
        for name, path in instances:
            cmd = [sys.executable, os.path.join(REPO, "solvers", solver, "run.py"), path]
            budget = budgets.get(name, args.time_limit_ms)
            if budget and solver != "vroom":
                cmd += ["--time-limit-ms", str(budget)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout or r.stderr).strip().splitlines()
            print(f"  {out[-1] if out else '(no output)'}")
        if not args.keep_up:
            compose(solver, "down")

    print("\n=== results/ summary ===")
    for solver in solvers:
        got = sorted(glob.glob(os.path.join(REPO, "results", solver, "*.json")))
        print(f"  {solver}: {len(got)} solution(s) -> results/{solver}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
