# PyVRP harness

[PyVRP](https://github.com/PyVRP/PyVRP) — a hybrid-genetic-search solver for hard-constrained VRPs
(CVRP, VRPTW, prize-collecting). PyVRP is a Python *library*, so it's wrapped in a tiny HTTP service
that speaks the [Standard I/O contract](../../docs/standard-io-contract.md). Custom-matrix mode: the
instance's raw-OSRM `distances` matrix is used directly, no map backend.

## Quick start

```bash
cd solvers/pyvrp
docker compose up -d --build      # builds python:3.12 + pyvrp, serves :5002

python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz -o /tmp/pb-0187.pyvrp.json

docker compose down
```

`run.py` POSTs the Standard Instance to the service; the service builds the PyVRP `Model`, solves, and
returns a [Standard Solution](../../docs/standard-io-contract.md).

## Files

- [`solve.py`](solve.py) — the PyVRP `Model` builder + version-sensitive route extraction, adapted from
  Routific's internal benchmark harness (Apache-2.0).
- [`server.py`](server.py) — Standard-contract HTTP wrapper (injects `minimize_vehicles`, returns a
  Standard Solution).

## Modeling notes

- **Time budget.** PyVRP is anytime; `run.py --time-limit-ms N` sets the solve budget (default is
  size-scaled). Reproducing published numbers requires the same per-problem budgets (published with the
  results).
- **`minimize_vehicles`.** A per-vehicle `fixed_cost` (`PYVRP_FIXED_COST`, default 15000) consolidates
  routes. It stays **below** the serve-a-visit prize (`PYVRP_PRIZE_FLOOR`, default 20000), so PyVRP
  never drops a servable stop to save a vehicle: **serve > vehicles > travel time**.
- **Capacity/demand** map to PyVRP integer load dimensions (scalar → 1-D; typed → sorted-key vector).
  Open routes use a shared 0-cost "open" depot. Multiple disjoint time windows are relaxed to their
  enclosing span. Pickup-delivery `precedence` is not modeled (the `public-benchmark` set has none).

## License

PyVRP is MIT-licensed and installed at build time (not redistributed here). See
[`../../THIRD-PARTY.md`](../../THIRD-PARTY.md).
