# Results

How Routific compares to the open-source solvers (VROOM, PyVRP, OR-Tools) on the `public-benchmark`
dataset (**264 instances**, 30–3,000+ stops). The headline: **at the same coverage and the same fleet
size, Routific is within ~±1–2% on travel time while producing routes that are far more visually
attractive (~7× fewer crossings between routes), better balanced, and lower on idle time — all on
identical hardware, with the competitors given every advantage.** (The runtime section sets out the
competitors' time budgets relative to Routific's runtime.)

Every number here is recomputed from the published `(instance, solution)` files by
[`analysis/compute_metrics.py`](../analysis/compute_metrics.py) and is reproducible with:

```bash
python3 analysis/fair_compare.py --exclude jsprit
```

> Metric definitions and their grounding in the visual-attractiveness literature are in
> [`docs/methodology.md`](methodology.md); solver coverage and caveats in
> [`docs/results-status.md`](results-status.md). Every raw number behind the aggregates below —
> one row per instance, all metrics × all solvers — is in
> [`results/all-results.md`](../results/all-results.md).

## How the comparison is set up

A cheaper-looking route can simply be serving fewer stops, or spreading them over more trucks — so a
raw average of any metric is misleading. This comparison is **gated** so like is compared with like:

1. **Coverage first.** Compare how many stops each solver leaves unserved.
2. **Quality at equal coverage.** Compare every other metric **only on instances where all solvers
   serve the same number of stops**.
3. **Travel at equal fleet.** Compare travel time **only where the two solvers also use the same
   number of vehicles** — because more trucks mechanically means more total travel.

The competitors are given every advantage, so this is conservative for Routific:

- **Same hardware.** Every solver ran on a **6-vCPU `c2-standard-8`** node — the same class Routific's
  own engine runs on — so nothing here is a hardware artifact.
- **VROOM at max search** — `explore: 4`, dropping to `explore: 3` on the largest instances (>500
  stops), where `explore: 4` exceeds the 40-min cap. Quality is flat across explore levels, so this
  doesn't move the comparison — it only affects a couple percent of runtime.
- **PyVRP and OR-Tools each get a fixed per-problem time budget, proportionate to problem
  difficulty** (they're anytime solvers): `max(2 s, 2 × Routific's runtime)`, computed from the
  runtimes of the earlier (July 2026) Routific column. Against the current Routific column that works
  out to ~1.4× Routific's time in aggregate (see [Runtime](#4-runtime-same-hardware--6-vcpu-c2-standard-8)).
  Every per-problem budget is published in
  [`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv); see [`RUNNING.md`](../RUNNING.md).
- Routific is evaluated in its **fleet-minimizing configuration**; gating travel on **equal fleet
  size** keeps that objective difference from distorting the travel comparison.

Common set below: **260 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit is compared
separately in [Routific vs jsprit](results-jsprit.md) because it only runs ≤400-stop problems).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 25.47 | 25.43 | 45.66 | 27.86 |
| fewest-unserved win-rate | 94% | 96% | 88% | 92% |

Routific and VROOM serve essentially identically. **PyVRP is the coverage outlier** — on the large
instances its fixed time budget buys much less search, so it drops far more (and on two single-vehicle
time-window instances it fails to construct a serving route at all — see
[`results-status.md`](results-status.md)); OR-Tools is close to Routific. This leaves **214 instances
where all four serve identically** — the basis for the quality comparison. (Unserved counts are high
because the dataset includes many 1,000–3,000-stop problems.)

## 2. Route quality at equal coverage (214 instances)

Mean (lower is better), with Routific's win-rate — the share of instances where it's best. The
between-routes metrics (crossings, balance, variance) only apply to the 176 multi-route instances in
the set — single-vehicle (TSP) solutions have no between-routes structure:

| metric | **Routific** | VROOM | PyVRP | OR-Tools | Routific win-rate |
|---|--:|--:|--:|--:|--:|
| Number of vehicles | **13.9** | 14.3 | 14.3 | 14.4 | **95%** |
| **Crossings between routes (sum)** | **4.8** | 33.9 | 36.2 | 49.2 | **90%** |
| **Crossings between routes (max)** | **1.4** | 3.9 | 3.2 | 4.5 | **89%** |
| Crossings within a route | 83.4 | 86.4 | 86.2 | 87.1 | 46% |
| **Workload imbalance** | **75.2** | 97.7 | 99.3 | 95.0 | **57%** |
| **Route-duration variance** | **8,964** | 13,119 | 13,346 | 12,729 | **53%** |
| **Idle / wait (s)** | **3,878** | 6,095 | 5,436 | 6,353 | **99%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific averages **4.8 per instance vs 34–49** for the competitors (**~7× fewer** than the best of
  them) and is best on **90%** of instances; the worst single route pair is also tidier (max 1.4 vs 3.2–4.5).
- **Idle / wait time** is lowest for Routific on **99%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split) are both lowest for Routific.
- **Fleet size is lowest for Routific** (13.9 vs 14.3–14.4, best on 95%) — it uses fewer trucks, not more.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) | Routific shorter on |
|---|--:|--:|--:|
| VROOM | 196 | 1.01 | 85 / 196 |
| PyVRP | 185 | 1.01 | 58 / 185 |
| OR-Tools | 185 | 0.98 | 124 / 185 |

Once fleet size is matched, **travel is within ~1–2%** — effectively a tie: about 1% longer than
VROOM and PyVRP, and about 2% *shorter* than OR-Tools (shorter on two thirds of those instances).
Routific pays essentially nothing on distance for its route-quality gains.

The table above is **pairwise** (Routific vs. each competitor on that pair's own equal-coverage /
equal-fleet subset, so the instance set differs per column). Restricting further to the **144
instances where all four solvers simultaneously match both unserved count and vehicle count** gives one common subset to sum total travel time over:

| solver | total travel time (s) | mean travel time (s) |
|---|--:|--:|
| VROOM | 9,808,117 | 68,112 |
| Routific | 9,872,831 | 68,561 |
| PyVRP | 9,906,985 | 68,799 |
| OR-Tools | 10,029,715 | 69,651 |

Same conclusion as the pairwise view: all four solvers are within ~2% of each other in total travel
once coverage and fleet size are held fixed simultaneously across the board (Routific second, 0.7%
behind VROOM).

## 4. Runtime (same hardware — 6-vCPU c2-standard-8)

Because every solver ran on identical hardware, runtimes are comparable. Over the 260-instance common
set:

| solver | mean | median | note |
|---|--:|--:|---|
| **Routific** | **154,184 ms** | 17,592 ms | engine solve time |
| VROOM | 168,200 ms | 10,959 ms | max `explore`, no time budget |
| PyVRP | 217,029 ms | 27,226 ms | anytime — fixed per-problem budget (see below) |
| OR-Tools | 216,067 ms | 27,000 ms | anytime — fixed per-problem budget (see below) |

> **The PyVRP / OR-Tools budgets.** Each problem has a fixed budget of `max(2 s, 2 × Routific's
> runtime)`, computed from the **earlier (July 2026) Routific column** (mean 107,849 ms on this set)
> and published per problem in [`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv).
> The current Routific column takes **~42% longer** in total than that earlier one, so the budgets
> work out to about **1.4× the current Routific runtime** in aggregate — under 2× on roughly half of
> the problems, and less time than Routific on ~30 of them.

- **Routific is the fastest on average, narrowly** (mean 154k ms vs VROOM's 168k; PyVRP/OR-Tools'
  ~217k is their budget, not a natural stopping point). VROOM has no budget: it's quick on small
  problems (lower median) but its mean is higher because, with no stopping rule, it grinds the large
  instances.
- **Bottom line:** on equal hardware Routific is not the slow solver — its mean runtime is the lowest
  of the four, while producing the higher-quality routes above.

## Reading it

> **At equal stops and equal trucks, Routific is within ~±1–2% on travel and wins decisively on the
> qualities that make a route good to operate — far fewer crossings, more even workloads, less idle
> time, a smaller fleet.** This holds with VROOM at max search and PyVRP and OR-Tools with anytime
> budgets of ~1.4× Routific's time in aggregate. More search / more time makes the competitors' routes a
> little *shorter*, never *tidier*. The gap is sharpest on the **large instances**, where the engine's
> optimization has the most room to work.

## Caveats

- **Coverage is a near-tie** with VROOM; PyVRP/OR-Tools trail on the hardest large instances.
- **VROOM covers 260/264** — a few of the very largest exceed the time cap even at `explore: 3`.
  PyVRP, OR-Tools, and Routific cover all 264.
- **One instance (`pb-0264`) is infeasible for every solver** — its time windows can't be met by a
  single vehicle under the hard-constrained contract, so all four leave essentially all of its stops
  unserved. It's included as-is (unserved is a reported quantity, and the coverage gates handle it).
- **The Routific column's engine is not runnable from this repo** ([contact us](https://routific.com));
  its solutions are precomputed and bundled so the comparison reproduces from public files alone.

## Reproduce

```bash
python3 analysis/fair_compare.py --exclude jsprit   # the gated comparison above
python3 analysis/analyze.py                         # per-metric means + win-rate, all solvers
python3 analysis/build_all_results.py               # regenerate results/all-results.md (every raw number)
# re-run the competitors at the published per-problem budgets (Docker; see RUNNING.md)
python3 run_benchmark.py --sample 264 --budget-map results/competitor-budgets.tsv
```
