#!/usr/bin/env python3
"""Import Routific's precomputed benchmark solutions from the internal DB and write
them as Standard Solutions under results/<solver>/.

Routific's v3 engine is not runnable from the public repo, so its results are
precomputed and bundled. This is an INTERNAL tool: it needs BENCHMARK_DATABASE_URL
and the private provenance map (pb-name -> internal problem id). Reproducers get
the committed Routific result files, not this script.

The stored solution is a per-vehicle array of {start_time, permutation}; the
permutation is the visit-index order, which maps straight to a Standard Solution
(the exporter preserved visit order).

  BENCHMARK_DATABASE_URL=... python3 import_routific_results.py \
      --benchmark-id 2078 --solver routific-v3-ls [--names pb-0013,pb-0064]
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(REPO, "datasets", "public-benchmark")
PROVENANCE = os.path.join(DATASET, "_provenance.private.csv")


def load_instance(name: str) -> dict:
    hits = glob.glob(os.path.join(DATASET, "*", f"{name}.json.gz"))
    if not hits:
        sys.exit(f"instance not found: {name}")
    with gzip.open(hits[0], "rb") as f:
        return json.load(f)


def psql_rows(dburl: str, sql: str) -> list[list[str]]:
    r = subprocess.run(["psql", dburl, "-tAF", "\t", "-c", sql], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"psql failed: {r.stderr.strip()}")
    return [ln.split("\t") for ln in r.stdout.strip().splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark-id", type=int, required=True)
    ap.add_argument("--solver", required=True, help="output solver name, e.g. routific-v3-ls")
    ap.add_argument("--names", help="comma-separated pb names (default: all in provenance)")
    args = ap.parse_args()

    dburl = os.environ.get("BENCHMARK_DATABASE_URL")
    if not dburl:
        sys.exit("set BENCHMARK_DATABASE_URL")

    prov = {r["name"]: r["source_instance_id"] for r in csv.DictReader(open(PROVENANCE))}
    names = args.names.split(",") if args.names else list(prov)
    src_by_name = {n: prov[n] for n in names if n in prov}
    ids = ",".join(src_by_name.values())

    rows = psql_rows(dburl, f"select problem_id, runtime, solution::text from results "
                            f"where benchmark_id={args.benchmark_id} and problem_id in ({ids}) "
                            f"and solution is not null;")
    sol_by_src = {r[0]: (int(r[1]), json.loads(r[2])) for r in rows}

    outdir = os.path.join(REPO, "results", args.solver)
    os.makedirs(outdir, exist_ok=True)
    written = 0
    for name, src in src_by_name.items():
        if src not in sol_by_src:
            print(f"  {name}: (no solution in benchmark {args.benchmark_id})")
            continue
        runtime_ms, raw = sol_by_src[src]
        n_visits = len(load_instance(name)["visits"])
        routes, served = [], set()
        for k, r in enumerate(raw):
            perm = r.get("permutation") or []
            if not perm:
                continue
            routes.append({"vehicle": k, "start_time": r.get("start_time"), "visits": perm})
            served.update(perm)
        unserved = [i for i in range(n_visits) if i not in served]
        std = {"instance": name, "solver": args.solver, "routes": routes, "unserved": unserved,
               "runtime_ms": runtime_ms, "meta": {"benchmark_id": args.benchmark_id}}
        with open(os.path.join(outdir, f"{name}.json"), "w") as f:
            json.dump(std, f, separators=(",", ":"))
        written += 1
        print(f"  {name}: routes={len(routes)} unserved={len(unserved)} runtime_ms={runtime_ms}")
    print(f"wrote {written} -> results/{args.solver}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
