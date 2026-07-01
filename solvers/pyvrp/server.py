#!/usr/bin/env python3
"""HTTP server exposing PyVRP over the Standard I/O contract.

  GET  /        -> readiness probe
  POST /solve   -> body: a Standard Instance (optional ?time_limit_ms=N)
                   returns: a Standard Solution

`solve.py` (Routific's PyVRP `Model` builder, adapted from the internal harness)
expects `secondary_objective.minimize_vehicles`; a Standard Instance carries
`minimize_vehicles` at top level, so we inject it before solving. Stdlib only.
"""
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import solve as solver

PORT = int(os.environ.get("PORT", "5002"))


def to_solution(instance: dict, summary: dict) -> dict:
    """solve.py summary (vehicle_routes / dropped) -> Standard Solution."""
    name = instance.get("name", "instance")
    routes = []
    for k, perm in enumerate(summary.get("vehicle_routes", [])):
        if not perm:
            continue
        routes.append({
            "vehicle": k,
            "start_time": instance["vehicles"][k].get("shift_start_time"),
            "visits": perm,
        })
    return {
        "instance": name,
        "solver": "pyvrp",
        "routes": routes,
        "unserved": summary.get("dropped", []),
        "runtime_ms": summary.get("solve_ms"),
        "meta": {k: summary.get(k) for k in ("duration", "service", "cost", "routes", "assigned", "unassigned")},
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"status": "ok"})

    def do_POST(self):
        try:
            q = parse_qs(urlparse(self.path).query)
            length = int(self.headers.get("Content-Length", 0))
            instance = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:  # noqa: BLE001
            self._send(400, {"error": f"bad request: {e}"})
            return
        try:
            # Standard Instance -> the shape solve.build_and_solve expects.
            instance["secondary_objective"] = {"minimize_vehicles": bool(instance.get("minimize_vehicles"))}
            tl_ms = int((q.get("time_limit_ms") or [0])[0]) or \
                solver.default_time_limit_ms(len(instance.get("visits", [])))
            summary, _ = solver.build_and_solve(instance, tl_ms)
            if summary.get("code") != 0:
                # No feasible solution found within the budget -> empty routes.
                n = len(instance.get("visits", []))
                self._send(200, {
                    "instance": instance.get("name", "instance"), "solver": "pyvrp",
                    "routes": [], "unserved": list(range(n)),
                    "runtime_ms": summary.get("solve_ms"),
                    "meta": {"code": summary.get("code"), "error": summary.get("error")},
                })
                return
            self._send(200, to_solution(instance, summary))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        sys.stderr.write("pyvrp-server: " + (fmt % args) + "\n")


if __name__ == "__main__":
    print(f"pyvrp-server listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
