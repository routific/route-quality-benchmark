#!/usr/bin/env python3
"""Solve one Standard Instance with VROOM and write a Standard Solution.

Prereq: the VROOM service is running (`docker compose up -d` in this dir).

  python3 run.py <instance.json[.gz]> [-o out.json] [--url http://localhost:3030]
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # solvers/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                   # solvers/vroom/
from common.standard_io import load_instance, write_solution, check_coverage  # noqa: E402
import adapter  # noqa: E402


def post(url, payload, timeout):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("-o", "--out")
    ap.add_argument("--url", default=os.environ.get("VROOM_URL", "http://localhost:3030"))
    ap.add_argument("--timeout", type=int, default=2460, help="HTTP timeout seconds "
                    "(60s above VROOM's own 40-min server cap, so its timeout fires first)")
    args = ap.parse_args()

    inst = load_instance(args.instance)
    name = inst.get("name") or os.path.basename(args.instance).split(".")[0]

    resp = post(args.url, adapter.to_request(inst), args.timeout)
    if resp.get("code"):
        print(f"VROOM error code={resp.get('code')}: {resp.get('error')}", file=sys.stderr)
        return 1

    sol = adapter.to_solution(inst, resp, name)
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
