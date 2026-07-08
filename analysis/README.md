# Analysis — route-quality metrics

The analyzer compares solver outputs on the qualities that make a route *good to operate* — not just
total time. Every metric is **recomputed from the `(instance, solution)` pair alone** (no solver
internals), so results are independently reproducible.

```bash
python3 analysis/analyze.py     # competitors + the combined "routific" best-of column (if present)
```

Outputs (printed + `results/_analysis/*.csv`): a **per-metric mean** table and a **win-rate** table.
There is deliberately **no single composite score** — the point is to show each dimension, not collapse
them. Runtime is intentionally **not** compared yet (see Caveats).

## Metrics (all lower-is-better)

Computed in [`compute_metrics.py`](compute_metrics.py). A *leg* is the straight segment between two
consecutive stops (using the anonymized coordinates); travel time uses the raw-OSRM `distances` matrix.

| Metric | Definition |
|---|---|
| **Total travel time** | Σ matrix travel time over every leg, incl. depot legs (start→first, last→end). Seconds. |
| **Number of vehicles** | Non-empty routes used. |
| **Crossings between routes (sum)** | Crossings between the visit→visit legs of **adjacent** routes, summed over adjacent route pairs. |
| **Crossings between routes (max)** | Max, over all legs, of how many crossings a single leg has with **adjacent** routes' legs. |
| **Crossings within a route** | Self-crossings: non-consecutive leg pairs within a route (depot legs incl.), excluding the first↔last wrap. |
| **Workload imbalance** | Σ over routes of \|route's visit-count − average visit-count\|. Unit: stops. |
| **Route-duration variance** | **Range** (max − min) of route working time (travel + service + idle) across routes. Seconds. |
| **Idle / wait time** | Total time drivers wait for a stop's time window to open. Seconds. |

These are **ported to match Routific's internal `engine-bench analyze compute`** (`fitness.rs` +
`solution_timeline.rs`): workload imbalance is `deviation_from_balance` (balances stop *count* per
route); route-duration variance is `max_duration_variance` (a max−min *range*, despite the name).
*Working time* of a route = travel + service + idle. Segment crossings use a proper
segment-intersection test (shared endpoints / collinear touches don't count).

**Route adjacency.** Inter-route crossings are counted only between **adjacent** routes — the
nearest-neighbor `VehicleAdjacency` graph (each visit links its route to the route of its nearest visit
in a *different* route; the graph is then made fully connected). Fidelity gap: the internal
`reroute_incompatible_edges` refinement (type/capacity/TW compatibility) is not yet ported.

**Applicability.** Inter-route crossings, workload imbalance, and route-duration variance are only
meaningful when a solution uses ≥2 routes, so those means and win-rates are taken over **multi-route
instances** only (reported as `n` in the CSVs). Travel time, vehicles, self-crossings, and idle apply
to every instance.

**Win rate** = share of applicable instances where a solver ties or beats all others on that metric
(ties count for each winner, so a row can exceed 100%).

## Why these metrics — grounding

"Visual attractiveness of vehicle routes" is a formal research area. Rossit et al. (2019, *Computers &
Operations Research*) survey it and define three properties of an attractive route, each of which these
metrics measure directly:

- **Non-crossing / non-overlapping** → *crossings between/within routes* (the classic "spaghetti"
  signal drivers and dispatchers react to).
- **Compactness** → *workload imbalance* and *route-duration variance* (tight, evenly-sized routes) —
  and, operationally, *idle time* (a compact, well-sequenced route waits less).
- **Low complexity** → fewer crossings and fewer vehicles for the same work.

Travel time is reported alongside so quality is never read in isolation from cost. The full narrative +
citations (incl. the 2025 *C&OR* driver-acceptance work and the Amazon human-similarity angle) live in
the methodology write-up (Slice 6).

## Caveats

- **Runtime is shown, on equal hardware.** Every solver ran on the same 6-vCPU `c2-standard-8` node, so
  runtimes are directly comparable (see the Runtime section of [`docs/results.md`](../docs/results.md)).
  The anytime solvers (PyVRP/OR-Tools) are *given* 2× Routific's runtime as their budget, so their times
  are 2× Routific by construction; VROOM (no budget, fixed `explore`) is the only independent competitor
  clock. jsprit is excluded from the timed comparison (its number includes the HTTP round-trip; it caps
  by iterations).
- **Routific** appears as a single column: its published **raw result files** (`results/routific/`) — one
  Standard Solution per instance. Anyone can recompute Routific's metrics from those solutions, exactly
  like the competitors. Routific's engine is not runnable from this repo (contact Routific).
