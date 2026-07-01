#!/usr/bin/env python3
"""Solve one Standard Instance with PyVRP and write a Standard Solution.

Prereq: the PyVRP service is running (`docker compose up -d --build` in this dir).
The server converts the Standard Instance and returns a Standard Solution.

  python3 run.py <instance.json[.gz]> [-o out.json] [--time-limit-ms N]
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # solvers/
from common.standard_io import load_instance, write_solution, check_coverage  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("-o", "--out")
    ap.add_argument("--url", default=os.environ.get("PYVRP_URL", "http://localhost:5002/solve"))
    ap.add_argument("--time-limit-ms", type=int, help="solve budget (default: size-scaled)")
    ap.add_argument("--timeout", type=int, default=3600, help="HTTP timeout seconds")
    args = ap.parse_args()

    inst = load_instance(args.instance)
    name = inst.get("name") or os.path.basename(args.instance).split(".")[0]

    url = args.url + (f"?time_limit_ms={args.time_limit_ms}" if args.time_limit_ms else "")
    req = urllib.request.Request(url, data=json.dumps(inst).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=args.timeout) as r:
        sol = json.loads(r.read())

    cov = check_coverage(inst, sol)
    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "results", sol["solver"], f"{name}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_solution(out, sol)
    print(f"{name}: routes={len(sol['routes'])} unserved={len(sol['unserved'])} "
          f"complete={cov['complete']} dupes={cov['has_duplicates']} "
          f"runtime_ms={sol.get('runtime_ms')} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
