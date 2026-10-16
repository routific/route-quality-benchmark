# OR-Tools harness

[Google OR-Tools](https://github.com/google/or-tools) routing solver, wrapped in a tiny HTTP service
that speaks the [Standard I/O contract](../../docs/standard-io-contract.md). Custom-matrix mode: the
instance's raw-OSRM `distances` matrix is used directly, no map backend.

> **Is this "Google's Route Optimization API"?** No. This is the open-source **OR-Tools** library
> (self-hosted, free). Google's hosted *Route Optimization* / *GMPRO* API is a separate commercial
> product built on related tech; it is not benchmarked here.

## Quick start

```bash
cd solvers/ortools
docker compose up -d --build      # python:3.12 + ortools, serves :5001

python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz -o /tmp/pb-0187.ortools.json

docker compose down
```

## Files

- [`solve.py`](solve.py) — the OR-Tools `RoutingModel` builder + route extraction, adapted from
  Routific's internal benchmark harness (Apache-2.0).
- [`server.py`](server.py) — Standard-contract HTTP wrapper.

## Modeling notes

- **Time budget.** `run.py --time-limit-ms N` (default size-scaled). Reproducing published numbers
  requires the same per-problem budgets (published in
  [`results/competitor-budgets.tsv`](../../results/competitor-budgets.tsv); `run_benchmark.py --budget-map` applies them).
- **`minimize_vehicles`.** `SetFixedCostOfAllVehicles(ORTOOLS_FIXED_COST, default 1e8)` consolidates
  routes. It sits **below** the visit drop penalty (`priority × 1e9`), so OR-Tools never drops a
  servable stop to save a vehicle: **serve > vehicles > travel time**.
- **Droppable visits** via `AddDisjunction` with a large penalty. Capacity/demand map to OR-Tools
  dimensions (scalar → 1-D; typed → per-key dimensions). Pickup-delivery `precedence` is not modeled
  (the `public-benchmark` set has none).

## License

OR-Tools is Apache-2.0 and installed at build time (not redistributed here). See
[`../../THIRD-PARTY.md`](../../THIRD-PARTY.md).
