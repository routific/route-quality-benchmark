#!/usr/bin/env python3
"""Solve one Standard Instance with jsprit and write a Standard Solution.

Prereq: the jsprit service is running (`docker compose up -d --build` in this dir).

  python3 run.py <instance.json[.gz]> [-o out.json] [--time-limit-ms N]

Note: jsprit does not report its own solve time, so runtime_ms here is client-side
wall-clock (localhost) — a close proxy for small/medium instances.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # solvers/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # solvers/jsprit/
from common.standard_io import load_instance, write_solution, check_coverage  # noqa: E402
import adapter  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("-o", "--out")
    ap.add_argument("--url", default=os.environ.get("JSPRIT_URL", "http://localhost:8080/solve"))
    ap.add_argument("--time-limit-ms", type=int, help="solve budget (default: jsprit's 2000 iterations)")
    ap.add_argument("--max-stops", type=int, default=int(os.environ.get("JSPRIT_MAX_STOPS", "400")),
                    help="skip instances larger than this — jsprit does not scale past ~400 stops")
    ap.add_argument("--force", action="store_true", help="run even if the instance exceeds --max-stops")
    ap.add_argument("--timeout", type=int, default=3600, help="HTTP timeout seconds")
    args = ap.parse_args()

    inst = load_instance(args.instance)
    name = inst.get("name") or os.path.basename(args.instance).split(".")[0]

    n_stops = len(inst.get("visits", []))
    if n_stops > args.max_stops and not args.force:
        print(f"{name}: SKIPPED (jsprit: {n_stops} stops > {args.max_stops}-stop cap; pass --force to run)")
        return 0

    payload = json.dumps(adapter.to_request(inst, args.time_limit_ms)).encode()
    req = urllib.request.Request(args.url, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=args.timeout) as r:
        resp = json.loads(r.read())
    runtime_ms = round((time.time() - t0) * 1000, 1)

    sol = adapter.to_solution(inst, resp, name, runtime_ms)
    cov = check_coverage(inst, sol)
    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "results", sol["solver"], f"{name}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_solution(out, sol)
    print(f"{name}: routes={len(sol['routes'])} unserved={len(sol['unserved'])} "
          f"complete={cov['complete']} dupes={cov['has_duplicates']} "
          f"runtime_ms={sol['runtime_ms']} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
