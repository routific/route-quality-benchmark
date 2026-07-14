#!/usr/bin/env python3
"""Emit results/all-results.md: one giant table, one row per instance.

Columns: instance descriptors (type / stops / vehicles available / min-vehicles flag)
followed by one group per metric, each group holding one sub-column per solver. Every
metric value is recomputed from the (instance, solution) pair via compute_metrics.compute,
so the table is fully reproducible:

    python3 analysis/build_all_results.py

Missing solver results (e.g. jsprit's partial coverage) render as blank cells. The footer
row is each solver's mean over the instances it actually solved.
"""
from __future__ import annotations
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_metrics import compute  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(REPO, "datasets", "public-benchmark")
RESULTS = os.path.join(REPO, "results")
OUT = os.path.join(RESULTS, "all-results.md")

SOLVERS = ["jsprit", "ortools", "pyvrp", "routific", "vroom"]

# (metric key, short header, formatter)
def _i(v):  # integer
    return "" if v is None else f"{round(v):,}"

def _f1(v):  # one decimal
    return "" if v is None else f"{v:,.1f}"

METRICS = [
    ("travel_time", "Travel time (s)", _i),
    ("num_vehicles", "Routes used", _i),
    ("num_unserved", "Unserved", _i),
    ("inter_route_crossings_sum", "Inter-route cross (sum)", _i),
    ("inter_route_crossings_max", "Inter-route cross (max)", _i),
    ("intra_route_crossings", "Intra-route cross", _i),
    ("workload_imbalance", "Workload imbalance", _f1),
    ("route_duration_variance", "Route-dur. variance (s)", _i),
    ("idle_time", "Idle time (s)", _i),
    ("runtime_ms", "Runtime (ms)", _i),
]


def load_instance(path: str) -> dict:
    with gzip.open(path, "rb") as f:
        return json.load(f)


def main() -> int:
    inst_files = {os.path.basename(p)[:-8]: p for p in glob.glob(os.path.join(DATASET, "*", "*.json.gz"))}
    names = sorted(inst_files)

    # metrics[name][solver] = dict or None
    metrics: dict[str, dict[str, dict | None]] = {}
    props: dict[str, dict] = {}
    for name in names:
        inst = load_instance(inst_files[name])
        props[name] = {
            "type": inst.get("type", ""),
            "stops": len(inst.get("visits", [])),
            "vehicles": len(inst.get("vehicles", [])),
        }
        metrics[name] = {}
        for s in SOLVERS:
            p = os.path.join(RESULTS, s, f"{name}.json")
            metrics[name][s] = compute(inst, json.load(open(p))) if os.path.exists(p) else None

    # ---- build HTML table ----
    ncols_metric = len(SOLVERS)
    parts = []
    parts.append('<table>')
    # header row 1: descriptors (rowspan 2) + metric group headers (colspan)
    parts.append("<thead>")
    r1 = ['<th rowspan="2">Instance</th>',
          '<th rowspan="2">Type</th>',
          '<th rowspan="2">Stops</th>',
          '<th rowspan="2">Vehicles avail.</th>']
    for _, label, _fmt in METRICS:
        r1.append(f'<th colspan="{ncols_metric}">{label}</th>')
    parts.append("<tr>" + "".join(r1) + "</tr>")
    # header row 2: solver names under each metric
    r2 = []
    for _ in METRICS:
        for s in SOLVERS:
            r2.append(f"<th>{s}</th>")
    parts.append("<tr>" + "".join(r2) + "</tr>")
    parts.append("</thead>")

    # ---- body ----
    parts.append("<tbody>")
    for name in names:
        p = props[name]
        cells = [f"<td>{name}</td>",
                 f"<td>{p['type']}</td>",
                 f'<td align="right">{p["stops"]}</td>',
                 f'<td align="right">{p["vehicles"]}</td>']
        for key, _label, fmt in METRICS:
            for s in SOLVERS:
                m = metrics[name][s]
                val = fmt(m[key]) if m is not None else ""
                cells.append(f'<td align="right">{val}</td>')
        parts.append("<tr>" + "".join(cells) + "</tr>")
    parts.append("</tbody>")
    parts.append("</table>")
    table_html = "\n".join(parts)

    n_solved = {s: sum(1 for n in names if metrics[n][s] is not None) for s in SOLVERS}
    coverage = ", ".join(f"{s} {n_solved[s]}/{len(names)}" for s in SOLVERS)

    md = f"""# All raw results — one row per instance

Every metric is **recomputed from the `(instance, solution)` pair** by
[`analysis/compute_metrics.py`](../analysis/compute_metrics.py) — see
[`analysis/README.md`](../analysis/README.md) for definitions. All metrics are **lower-is-better**.
Regenerate with `python3 analysis/build_all_results.py`.

- **{len(names)} instances.** Solver coverage: {coverage}. Blank cells = solver has no result for that instance.
- **Descriptors:** `Type` (tsp/cvrp/cvrptw/vrp/vrptw), `Stops` (visits), `Vehicles avail.` (fleet size in the
  instance, not routes used).
- **Routes used** = non-empty routes; **Unserved** = orders left unassigned. Read those two together on
  min-veh instances — a route "saved" by dropping an order is not a saved route.
- The crossing / imbalance / route-duration-variance metrics are only meaningful for multi-route
  solutions; single-route rows will show 0.

{table_html}
"""
    with open(OUT, "w") as f:
        f.write(md)
    print(f"wrote {OUT}  ({len(names)} rows, {len(METRICS)} metrics x {len(SOLVERS)} solvers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
