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
import glob
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
    ap.add_argument("--time-limit-ms", type=int, help="solve budget for pyvrp/ortools/jsprit")
    ap.add_argument("--keep-up", action="store_true", help="leave services running afterwards")
    args = ap.parse_args()

    solvers = [s for s in args.solvers.split(",") if s in SOLVERS]
    if args.instances:
        names = args.instances.split(",")
    elif args.sample:
        files = sorted(glob.glob(os.path.join(DATASET, "*", "*.json.gz")))[: args.sample]
        names = [os.path.basename(f).split(".")[0] for f in files]
    else:
        names = DEFAULT_INSTANCES
    instances = [(n, find_instance(n)) for n in names]

    print(f"solvers: {solvers}\ninstances ({len(instances)}): {names}")
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
            if args.time_limit_ms and solver != "vroom":
                cmd += ["--time-limit-ms", str(args.time_limit_ms)]
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
