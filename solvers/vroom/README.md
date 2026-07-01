# VROOM harness

[VROOM](https://github.com/VROOM-Project/vroom) (Vehicle Routing Open-source Optimization Machine),
run in **custom-matrix mode**: each request carries the instance's raw-OSRM `distances` matrix, so
there is no OSRM/map backend. VROOM is featherweight this way — tens of MB of RAM, milliseconds per
solve on typical instances — and runs on a laptop.

## Quick start

```bash
cd solvers/vroom
docker compose up -d            # pulls ghcr.io/vroom-project/vroom-docker:v1.15.0, serves :3030

# solve one Standard Instance -> Standard Solution
python3 run.py ../../datasets/public-benchmark/tsp/pb-0054.json.gz -o /tmp/pb-0054.vroom.json

docker compose down             # when finished
```

`run.py` reads a Standard Instance (`.json` or `.json.gz`), converts it to a VROOM request
([`adapter.py`](adapter.py)), POSTs to the local service, and writes a
[Standard Solution](../../docs/standard-io-contract.md).

## Configuration

- **Image:** `ghcr.io/vroom-project/vroom-docker:v1.15.0` (see [`docker-compose.yml`](docker-compose.yml)).
- **`explore: 2`** in [`conf/config.yml`](conf/config.yml) — the value behind the published results.
  VROOM has no per-problem time budget, so `explore` (search level 0–5, server-wide) is the only
  effort lever; level 5 exploded on the 3,000-stop tail. Raise it for higher-quality (slower) solves.

## Modeling notes

- **Hard constraints only.** Standard Instances are already the hard-constrained form, so nothing is
  skipped. Capacity/demand map to VROOM integer amount vectors (scalar → 1-D; typed → sorted-key
  vector; uncapacitated vehicles in a capacitated instance get an effectively-infinite amount).
- **Open routes** (null `start_location`/`end_location`) omit `start_index`/`end_index`. Null shift/
  window bounds are filled against the instance time horizon.
- **`minimize_vehicles`:** each vehicle gets a fixed cost (`VROOM_FIXED_COST`, default `1e8`) so VROOM
  consolidates routes — its *default* objective minimizes travel time, not vehicle count. VROOM
  maximizes assigned tasks before minimizing cost, so the fixed cost never drops a servable visit to
  save a vehicle (hierarchy **serve > vehicles > travel time**). Verified: on a minimize-vehicles
  instance the fixed cost cut routes 2 → 1 with unserved unchanged. Work-balance is not modeled.
- **Not modeled:** pickup-delivery `precedence` (the `public-benchmark` set has none).

## License

VROOM is BSD-2-Clause; the Docker image is pulled at runtime, not redistributed here. See
[`../../THIRD-PARTY.md`](../../THIRD-PARTY.md).
