# jsprit harness

[jsprit](https://github.com/graphhopper/jsprit) — a Java toolkit for rich VRPs (GraphHopper). It runs
as an HTTP service; [`adapter.py`](adapter.py) converts a Standard Instance to jsprit's native request
and its response back to a [Standard Solution](../../docs/standard-io-contract.md). Custom-matrix mode:
the instance's raw-OSRM `travel_times` matrix is used directly, no map backend.

## Quick start

```bash
cd solvers/jsprit
docker compose up -d --build     # gradle shadowJar -> JRE image; first build takes a few minutes

python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz -o /tmp/pb-0187.jsprit.json

docker compose down
```

## Files

- `src/…`, `build.gradle`, `Dockerfile` — the jsprit HTTP service (Javalin), from Routific's internal
  `jsprit-service` (Apache-2.0). Runs with `-Xmx4g`.
- [`adapter.py`](adapter.py) — Standard ↔ jsprit request/response.

## Modeling notes & limitations

- **Scale cap.** jsprit's runtime grows steeply with problem size; the benchmark **limits jsprit to
  ≲400 stops** — larger instances are skipped by the runner (they don't finish in a comparable budget).
- **Single capacity dimension.** jsprit here models one load dimension, so a **typed (multi-dimension)**
  capacity/demand is collapsed to a scalar (sum of dimensions) — an approximation for multi-compartment
  instances.
- **`minimize_vehicles`.** A per-vehicle fixed cost of `maxCost × 20` (max matrix entry) pushes jsprit
  toward fewer vehicles; jsprit strongly prefers serving all jobs, so this consolidates without dropping
  servable stops (**serve > vehicles > travel time**).
- **Open routes** (null `end_location`) set `returnToDepot=false`; a null `start_location` falls back to
  the end depot (jsprit requires a start). Pickup-delivery `precedence` is not modeled.
- **Runtime.** jsprit doesn't report its own solve time, so `runtime_ms` is client-side wall-clock.

## License

jsprit is Apache-2.0 (built at image-build time, not redistributed here). See
[`../../THIRD-PARTY.md`](../../THIRD-PARTY.md).
