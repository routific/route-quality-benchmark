# Standard I/O Contract

This document is the **foundation** of the repository. Every dataset instance, every solver
adapter, and the analyzer all conform to the two schemas defined here:

- **Standard Instance** — one VRP problem to solve.
- **Standard Solution** — one solver's answer to a Standard Instance.

Defining these first is deliberate: because the instance schema **enumerates exactly which fields
are published**, PII removal (street addresses, internal identifiers) is a *designed-in property of
the format*, not an afterthought during export. See [Excluded fields](#fields-intentionally-excluded).

Machine-readable versions: [`schema/instance.schema.json`](../schema/instance.schema.json),
[`schema/solution.schema.json`](../schema/solution.schema.json). Worked examples:
[`schema/examples/`](../schema/examples/).

---

## 1. Standard Instance

A single JSON object. Locations are an **index space**: `vehicles` and `visits` refer to entries in
`locations` by integer index, and `distances` is the travel-time matrix over that same index space.

```jsonc
{
  "name": "pb-0001",                 // stable, opaque public instance id
  "type": "cvrptw",                  // tsp | vrp | cvrp | vrptw | cvrptw | pdp | pdptw

  "locations": [                     // index space; coordinates ONLY (no address/name)
    { "lat": 43.0727, "lng": -89.3839 }
  ],

  "vehicles": [
    {
      "id": "veh-0",
      "start_location": 0,           // index into locations, or null (open start)
      "end_location": 0,             // index into locations, or null (open end)
      "shift_start_time": 28800,     // seconds
      "shift_end_time": 61200,       // seconds, or null (open)
      "capacity": 100                // number | { "<key>": number } | null (uncapacitated)
    }
  ],

  "visits": [
    {
      "id": "visit-0",
      "location": 1,                 // index into locations
      "duration": 300,               // service time, seconds
      "time_windows": [              // [] = unconstrained
        { "start": 32400, "end": 46800 }   // seconds; start/end may be null
      ],
      "demand": 20,                  // number | { "<key>": number } | null
      "precedence": null             // null, or a pickup-delivery precedence object
    }
  ],

  "distances": [[0, 540], [560, 0]], // N x N raw-OSRM travel time in SECONDS (N = locations.length)

  "minimize_vehicles": true          // the one retained objective: minimize the fleet size used
}
```

### Field notes & real-world variance

The published set is derived from anonymized real customer problems, so the schema must admit the
variance actually present in the data:

- **`capacity` / `demand`** — three forms: a **scalar** (single dimension), a **typed object**
  `{ "<key>": number }` (multiple capacity dimensions, e.g. weight + volume), or **null**
  (uncapacitated / no demand). An empty object `{}` means "typed but unconstrained".
- **`time_windows[].start` / `.end`** — integer **seconds**. Most instances use seconds-relative to
  the planning horizon; a small number carry absolute unix-epoch values. Solvers only need the values
  to be internally consistent with `shift_*_time`; normalization is handled at export.
- **`distances`** — **raw OSRM** travel time (no ML/traffic ETA adjustment), in seconds. This is the
  single source of truth all solvers consume, so cross-solver comparisons isolate *routing algorithm
  quality* from ETA methodology.
- **`minimize_vehicles`** — the single retained objective flag. `true` ⇒ using fewer vehicles is
  preferred (all else equal); `false` ⇒ fleet size is not part of the objective.

### Simplifications applied at export

To keep the benchmark universal and fair across solvers that model only hard constraints, several
Routific-specific / soft fields are dropped when producing Standard Instances. This is a deliberate
normalization, documented here for transparency:

| Dropped field | Effect | Instances affected (of 200) |
|---|---|---|
| `etas_options.*` (soft slack) | Instances published as the **hard-constrained** version (soft lateness / overtime / capacity-overload removed), so every solver competes on the same hard problem. | 28 lateness, 36 overtime, 19 cap-overload, 7 squash |
| `visits[].priority` | All stops treated as **equal priority**. | 9,595 visits had non-default priority |
| `vehicles[].speed` | Fleet normalized to **uniform speed** (effective time = `distances[i][j]`). | 31 non-unit speed; 24 mixed-speed fleets |
| `secondary_objective.*` except `minimize_vehicles` | Distance / balance / cluster-overlap objectives dropped; only fleet-size minimization retained. | all 245 |

### Fields intentionally excluded

These exist in Routific's internal instance format and are **removed** to produce a Standard Instance.
Because the contract lists them here explicitly, the exporter's job is unambiguous:

| Internal field | Why removed |
|---|---|
| `locations[].name` | **PII** — real street address (present in nearly all raw instances). Removed entirely. |
| `locations[].id` | Internal opaque token, redundant with the positional index. |
| `user_id`, `job_id` | Customer/job linkage (DB-only; never emitted). |
| `original_problem_id` | Links back to the pre-anonymization customer problem; kept private, never published. |

> Coordinates in `locations` are the **donut-geomasked** coordinates (displaced from the real
> location); with `name` removed and coordinates masked, an instance is anonymized. See the dataset
> methodology doc for the masking details.

---

## 2. Standard Solution

A single JSON object describing one solver's answer to one Standard Instance. A route is an **ordered
permutation of visit indices** — the core artifact used to recompute every quality metric.

```jsonc
{
  "instance": "pb-0001",             // Standard Instance "name" this solves
  "solver": "vroom",                 // vroom | pyvrp | ortools | jsprit | routific-v3 | ...
  "routes": [
    {
      "vehicle": 0,                  // index into instance.vehicles
      "start_time": 30000,           // seconds
      "visits": [3, 1, 5, 2]         // ordered permutation of indices into instance.visits
    }
  ],
  "unserved": [7, 9],                // visit indices left unassigned
  "runtime_ms": 1240,                // algorithm solve time (exclude network/IO latency)
  "meta": {}                         // optional solver-reported stats (free-form)
}
```

- A vehicle that serves nobody may be omitted from `routes` or included with an empty `visits`.
- Every visit index appears **exactly once** across all `routes[].visits` ∪ `unserved`.
- `runtime_ms` is the solver's own algorithm time, so speed is comparable across solvers.

The metrics analyzer ([`analysis/`](../analysis/)) reconstructs the full timeline from `(instance, solution)` alone — no
solver internals required — which is what makes results independently reproducible.

---

## Versioning

This contract is versioned. Breaking changes bump `CONTRACT_VERSION` (see the JSON Schemas'
`$id`). Current: **v1**.
