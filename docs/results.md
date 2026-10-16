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
  difficulty** (they're anytime solvers): `max(2 s, 2 × the current Routific runtime)` on that
  problem — they were rerun in October 2026 on the same `c2-standard-8` pool against the current
  Routific column (see [Runtime](#4-runtime-same-hardware--6-vcpu-c2-standard-8)). Every per-problem
  budget is published in [`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv); see
  [`RUNNING.md`](../RUNNING.md). The two longest-running instances, `pb-0089` and `pb-0102` (2,255 and 2,380
  visits), have no PyVRP/OR-Tools result and are excluded from the competitor comparisons (Routific
  and VROOM still cover them).
- Routific is evaluated in its **fleet-minimizing configuration**; gating travel on **equal fleet
  size** keeps that objective difference from distorting the travel comparison.

Common set below: **258 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit is compared
separately in [Routific vs jsprit](results-jsprit.md) because it only runs ≤400-stop problems).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 25.66 | 25.63 | 39.98 | 28.06 |
| fewest-unserved win-rate | 94% | 96% | 89% | 92% |

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
| Number of vehicles | **13.1** | 13.4 | 13.4 | 13.6 | **94%** |
| **Crossings between routes (sum)** | **4.6** | 33.9 | 33.2 | 49.1 | **91%** |
| **Crossings between routes (max)** | **1.4** | 3.9 | 3.5 | 4.6 | **90%** |
| Crossings within a route | 78.1 | 81.0 | 78.9 | 80.8 | 42% |
| **Workload imbalance** | **73.2** | 92.4 | 96.8 | 90.3 | **59%** |
| **Route-duration variance** | **8,695** | 12,575 | 13,303 | 12,282 | **54%** |
| **Idle / wait (s)** | **3,878** | 6,095 | 5,438 | 6,380 | **99%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific averages **4.6 per instance vs 33–49** for the competitors (**~7× fewer** than the best of
  them) and is best on **91%** of instances; the worst single route pair is also tidier (max 1.4 vs 3.5–4.6).
- **Idle / wait time** is lowest for Routific on **99%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split) are both lowest for Routific.
- **Fleet size is lowest for Routific** (13.1 vs 13.4–13.6, best on 94%) — it uses fewer trucks, not more.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) | Routific shorter on |
|---|--:|--:|--:|
| VROOM | 194 | 1.01 | 83 / 194 |
| PyVRP | 185 | 1.01 | 52 / 185 |
| OR-Tools | 183 | 0.99 | 122 / 183 |

Once fleet size is matched, **travel is within ~1–2%** — effectively a tie: about 0.5% longer than
VROOM, about 1% longer than PyVRP, and about 1.5% *shorter* than OR-Tools (shorter on two thirds of
those instances).
Routific pays essentially nothing on distance for its route-quality gains.

The table above is **pairwise** (Routific vs. each competitor on that pair's own equal-coverage /
equal-fleet subset, so the instance set differs per column). Restricting further to the **144
instances where all four solvers simultaneously match both unserved count and vehicle count** gives one common subset to sum total travel time over:

| solver | total travel time (s) | mean travel time (s) |
|---|--:|--:|
| VROOM | 9,708,325 | 67,419 |
| PyVRP | 9,777,499 | 67,899 |
| Routific | 9,781,450 | 67,927 |
| OR-Tools | 9,924,177 | 68,918 |

Same conclusion as the pairwise view: all four solvers are within ~2% of each other in total travel
once coverage and fleet size are held fixed simultaneously across the board (Routific 0.8% behind
VROOM and level with PyVRP — 0.04% apart — and 1.4% ahead of OR-Tools).

## 4. Runtime (same hardware — 6-vCPU c2-standard-8)

Because every solver ran on identical hardware, runtimes are comparable. Over the 258-instance common
set:

| solver | mean | median | note |
|---|--:|--:|---|
| **Routific** | **132,758 ms** | 15,816 ms | engine solve time |
| VROOM | 156,996 ms | 10,762 ms | max `explore`, no time budget |
| PyVRP | 266,780 ms | 31,719 ms | anytime — fixed per-problem budget (see below) |
| OR-Tools | 265,847 ms | 31,633 ms | anytime — fixed per-problem budget (see below) |

> **The PyVRP / OR-Tools budgets.** Each problem has a fixed budget of `max(2 s, 2 × the current
> Routific runtime)` on that problem (mean 265,823 ms on this set), published per problem in
> [`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv); both solvers were rerun at
> these budgets in October 2026 on the same `c2-standard-8` pool. The reported runtimes sit at their budgets: OR-Tools within 0.3% on every instance, PyVRP
> within 2.5% on every instance but one — PyVRP's reported runtime includes its post-solve repair of
> dropped visits, so on `pb-0240` (1,925 dropped, then 900 repaired) it exceeds the budget by about 5%.

- **Routific is the fastest on average** (mean 133k ms vs VROOM's 157k; PyVRP/OR-Tools'
  ~266k is their budget, not a natural stopping point). VROOM has no budget: it's quick on small
  problems (lower median) but its mean is higher because, with no stopping rule, it grinds the large
  instances.
- **Bottom line:** on equal hardware Routific is not the slow solver — its mean runtime is the lowest
  of the four, while producing the higher-quality routes above.

## Reading it

> **At equal stops and equal trucks, Routific is within ~±1–2% on travel and wins decisively on the
> qualities that make a route good to operate — far fewer crossings, more even workloads, less idle
> time, a smaller fleet.** This holds with VROOM at max search and PyVRP and OR-Tools given anytime
> budgets of 2× Routific's own runtime on each problem. More search / more time makes the competitors' routes a
> little *shorter*, never *tidier*. The gap is sharpest on the **large instances**, where the engine's
> optimization has the most room to work.

## Caveats

- **Coverage is a near-tie** with VROOM; PyVRP/OR-Tools trail on the hardest large instances.
- **VROOM covers 260/264** — a few of the very largest exceed the time cap even at `explore: 3`.
  PyVRP and OR-Tools cover 262/264: the two longest-running instances, `pb-0089` and `pb-0102` (2,255 and
  2,380 visits), have no PyVRP/OR-Tools result and are excluded from the competitor comparisons.
  Routific covers all 264 (and VROOM covers those two).
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
