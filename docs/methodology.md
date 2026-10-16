# Methodology

Why this benchmark is set up the way it is — how the dataset was built, how the problems were chosen,
and why the metrics are the ones we measure. The goal is a benchmark that is **reproducible** (anyone
can re-run the competitors and recompute every number) and **defensible** (the metrics map to
published research on what makes a route good, not to a formula we invented).

This document is the narrative. The exact definitions live next to the code:
- **Data contract** — [`docs/standard-io-contract.md`](standard-io-contract.md)
- **Dataset specifics** (layout, matrices, OSRM version, anonymization) — [`datasets/public-benchmark/README.md`](../datasets/public-benchmark/README.md)
- **Metric math** — [`analysis/README.md`](../analysis/README.md)

---

## 1. Dataset construction

### 1.1 Source and selection

The `public-benchmark` dataset is **264 real-world VRP instances** derived from Routific customer
delivery problems — not synthetic or randomly generated. Real instances matter: synthetic VRPs
(uniform points on a square) don't have the geographic clustering, time-window structure, or
capacity mixes that make real routing hard and that visual-attractiveness metrics are meant to
capture.

Instances were selected by **stratified sampling** from the population of customer problems so the set
is representative rather than cherry-picked:

- **Size strata.** The set spans small to very large problems — 37 instances under 50 stops, 84 in the
  50–200 range, and 143 with 200+ (up to a 3,577-location problem). This keeps the benchmark honest
  about how solvers scale, not just how they do on toy sizes.
- **Constraint strata.** Problems are drawn across VRP families so no single constraint dominates:
  CVRP (120), VRPTW (63), plain multi-vehicle VRP (46), CVRPTW (23), and TSP (12). Types are assigned
  **from instance content** by [`tools/vrp_classify.py`](../tools/vrp_classify.py), not from any source
  label, so the taxonomy is reproducible from the published files alone. A batch of **19
  single-vehicle instances** (`pb-0246`–`pb-0264`, 31–120 stops) was added 2026-07-08 through the
  same anonymization pipeline.
- **Near-duplicate removal.** Highly similar problems were de-duplicated so the sample doesn't
  over-weight one customer's recurring route shape.

The per-instance breakdown is in [`datasets/public-benchmark/manifest.csv`](../datasets/public-benchmark/manifest.csv)
(name, type, sizes, feature flags). It carries **no** customer or job linkage.

### 1.2 Anonymization

Because the instances are customer-derived, they are anonymized before publication. The full
description is in the [dataset README](../datasets/public-benchmark/README.md#anonymization); in short:

- **Coordinates are donut-geomasked.** Each stop is displaced from its true position by a random
  offset drawn from an annulus (a "donut" — a minimum offset so no point stays exactly put, up to a
  maximum). The displacement radius is **density-adaptive**: it scales inversely with local population
  density (denser area → smaller offset, so the mask never moves a stop across a very different
  neighborhood), clamped to a **50 m – 3 km** band. Co-located stops (e.g. two orders at one address)
  are displaced together so their coincidence is preserved. The offset is drawn from a **deterministic
  per-instance seed**, so the masking is reproducible but not invertible without the seed. This is the
  standard geomasking approach used in health-geography for protecting patient addresses, applied here
  to delivery stops.
- **Addresses and identifiers removed.** The Standard Instance format carries **coordinates only** — no
  street address, and ids are opaque sequential labels. No `user_id` / `job_id` / original problem id
  is published. (Verified: 0 residual address strings across all 264 files.)

The masking preserves what the benchmark measures — relative geometry, clustering, and travel times
between stops — while destroying the ability to recover a real customer's stop.

### 1.3 Travel-time matrices

Every instance ships a pre-computed **N×N travel-time matrix** (`distances`, in seconds) so all solvers
see the *same* problem and no one needs a routing backend to reproduce results. The matrices are
**raw OSRM** road-network times (Contraction Hierarchies over OpenStreetMap extracts) with **no ML/ETA
adjustment** — see the [dataset README](../datasets/public-benchmark/README.md#matrices) for the OSRM
version and regional extract dates. Using one raw matrix per instance for every solver **isolates
routing-algorithm quality from ETA methodology**: differences in the results come from how a solver
sequences and assigns stops, not from whose travel-time model is better.

Per the data contract, the published instances are the **hard-constrained** form — soft-constraint
allowances are removed, stop priorities are equal, and vehicle speed is uniform — so every solver faces
exactly the same problem.

---

## 2. Why these metrics

Total travel time is the obvious VRP objective, but it is not the only thing that makes a route *good
to operate*. A route can be short on paper yet cross itself, zig-zag between neighborhoods, or load one
driver far heavier than another — all of which dispatchers and drivers reject in practice. The
benchmark therefore measures **route quality** across several dimensions and reports travel time
alongside, rather than collapsing everything into one score (there is deliberately **no composite
score** — the point is to show each dimension).

### 2.1 Grounding: visual attractiveness

"Visual attractiveness of vehicle routes" is a formal research area, surveyed by **Rossit et al. (2019,
*Computers & Operations Research* 103, 13–34)**, which identifies the properties of an attractive
route. Each maps directly to a metric we compute:

| Attractiveness property (Rossit et al.) | Metric(s) here |
|---|---|
| **Non-crossing / non-overlapping** | crossings *between* routes (sum, max) and *within* a route |
| **Compactness** (tight, evenly-sized routes) | workload imbalance, route-duration variance; operationally, idle/wait time |
| **Low complexity** (fewer, simpler routes) | number of vehicles, and fewer crossings for the same work |

These are not aesthetic niceties: crossing and non-compact routes correlate with driver rejection and
operational friction, which is why route *appearance* is an active thread in the routing literature
(including recent work on designing routes to improve **driver acceptance**, and the human-similarity
framing of the **Amazon Last Mile Routing Research Challenge**, Merchán et al. 2022). Travel time is
reported next to every quality metric so route quality is never read in isolation from cost.

### 2.2 How the metrics are computed

Every metric is **recomputed from the `(instance, solution)` pair alone** — no solver internals — so
any result is independently reproducible from the published files. The exact definitions (segment-
intersection test for crossings, nearest-neighbor route adjacency, the balance and duration-variance
formulas) are in [`analysis/README.md`](../analysis/README.md), and they are **ported to match
Routific's internal analyzer** so the public numbers line up with the internal ones.

### 2.3 What we deliberately don't do

- **No composite score.** Collapsing quality into one number hides the trade-offs; we show the
  dimensions.
- **Runtime is compared on equal hardware.** Every solver ran on the same 6-vCPU `c2-standard-8` node,
  so runtimes are directly comparable — see the Runtime section of [`docs/results.md`](results.md).
  (The anytime solvers' times are set by a fixed per-problem budget, proportionate to problem
  difficulty: `max(2 s, 2 × the current Routific runtime)` — PyVRP and OR-Tools were rerun at it in
  October 2026 on the same `c2-standard-8` pool. The only exception is the two largest instances,
  pb-0089 and pb-0102, which keep their July solutions at 2× the July Routific runtime (0.54 h and
  0.77 h, about 0.8× the current Routific runtime). Every per-problem budget is published in
  [`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv). VROOM, with no budget, is the
  only independent competitor clock.)
- **No ETA/traffic modeling.** Raw OSRM only — quality is judged on the routing decisions, not the
  travel-time model.

---

## 3. Reproducing it

The competitors are fully reproducible from this repo: `run_benchmark.py` solves every instance in
Docker at the published per-problem budgets ([`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv))
and `analysis/analyze.py` recomputes the tables (see [`RUNNING.md`](../RUNNING.md)). Routific's
own engine is **not runnable from this repo**; its results are published as Standard Solutions so its
metrics can be recomputed exactly like any competitor's — see
[`docs/results-status.md`](results-status.md) for coverage and [the README](../README.md#running-the-routific-engine)
for how to run the engine in an isolated environment.
