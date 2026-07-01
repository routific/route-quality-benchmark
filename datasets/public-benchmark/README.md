# `public-benchmark` dataset

**200 anonymized, real-world VRP instances** derived from Routific customer delivery problems, each
carrying a pre-computed **raw-OSRM** travel-time matrix. This is the routific (customer-derived)
dataset for the benchmark. Every instance conforms to the
[Standard Instance contract](../../docs/standard-io-contract.md).

## Layout

Instances are segregated by VRP type (classification derived purely from instance content by
[`tools/vrp_classify.py`](../../tools/vrp_classify.py)):

| type | count | meaning |
|---|---:|---|
| `cvrp`   | 84 | capacity, no time windows |
| `vrptw`  | 53 | time windows, no capacity |
| `vrp`    | 46 | multi-vehicle, no capacity/TW |
| `cvrptw` | 14 | capacity + time windows |
| `tsp`    | 3  | single vehicle, no capacity/TW |
| **total** | **200** | |

Size spread: **29** instances < 50 visits, **73** with 50–200, **98** with 200+.

```
public-benchmark/
├── cvrp/     pb-XXXX.json.gz …
├── vrptw/    …
├── vrp/      …
├── cvrptw/   …
├── tsp/      …
└── manifest.csv
```

## Reading an instance

Instances are stored **gzipped + minified** (`.json.gz`) — the matrices are large (up to a
3,577×3,577 problem), so the full set is ~294 MB gzipped vs ~1.4 GB pretty-printed. The `.gz` is only
on-disk encoding; the content is exactly the [Standard Instance](../../docs/standard-io-contract.md).

```python
import json, gzip
inst = json.load(gzip.open("datasets/public-benchmark/cvrp/pb-0002.json.gz", "rb"))
```
```bash
gzip -dc datasets/public-benchmark/cvrp/pb-0002.json.gz | jq .type
```

## `manifest.csv`

One row per instance: `name, type, num_visits, num_vehicles, num_locations, has_capacity,
has_time_windows, has_pdp, minimize_vehicles`. Contains **no** customer/job linkage.

## Anonymization

- **Coordinates** are **donut-geomasked** (displaced from their true location; density-adaptive
  radius, 50 m–3 km) — see the dataset methodology doc (Slice 6).
- **Street addresses removed.** The Standard Instance format carries coordinates only; the address
  field that existed in 181/200 source instances is dropped by construction (verified: 0 residual
  address strings across all 200 files).
- **Identifiers anonymized.** Vehicle/visit ids are sequential labels (`veh-N`, `visit-N`); instance
  names are opaque (`pb-XXXX`). No `user_id` / `job_id` / `original_problem_id` is published.

> ⚠️ **Pre-publication gate — verify coordinate masking.** These files were generated from cached
> instances that carry `original_problem_id` (i.e. the masking pipeline created them), but the actual
> coordinate displacement was **not** independently re-verified during this build. Confirm coords are
> genuinely displaced from the originals before any public release.

## Matrices

`distances` is an N×N matrix of **raw OSRM** travel time in **seconds** (no ML/traffic ETA
adjustment), N = `locations.length`. Using one raw matrix per instance for every solver isolates
routing-algorithm quality from ETA methodology.

### OSRM map version

Matrices were computed with **OSRM `v6.0.0`** (`project-osrm/osrm-backend`, Contraction Hierarchies,
`--max-table-size 8000`) over **Geofabrik `<region>-latest.osm.pbf`** extracts. The dataset spans six
regions; extract build dates (read from Routific's `kstaging` OSRM deployments):

| region | instances\* | OSM extract build date |
|---|---:|---|
| europe            | 86 | 2026-05-10 |
| north-america     | 76 | 2026-06-25 |
| australia-oceania | 24 | 2026-06-25 |
| africa            | 11 | 2026-06-25 |
| south-america     |  2 | 2026-06-25 |
| asia              |  1 | 2026-06-25 |

\*bucketed by first-stop coordinate. Matrices were generated during dataset construction (~2026-06-24/25)
via map-service → the regional OSRM above. Europe's 2026-05-10 extract predates construction (exact
match); the other regions were rebuilt on 2026-06-25 (the construction window), so their
extract-vs-matrix alignment is approximate to that date. Re-fetching the same Geofabrik region extract
reproduces the routing.

## Simplifications

Per the contract, these instances are the **hard-constrained** form (soft `etas_options` removed),
with equal stop priority and uniform vehicle speed. See
[Simplifications applied at export](../../docs/standard-io-contract.md#simplifications-applied-at-export).

## License

**CC BY-NC 4.0** — Attribution + NonCommercial ([full text](LICENSE)). Required attributions on any
use/redistribution:

- `public-benchmark dataset © Routific, licensed CC BY-NC 4.0.`
- `Produced using street network data © OpenStreetMap contributors, under the ODbL.`

See the repo-root [`NOTICE`](../../NOTICE) for details.
