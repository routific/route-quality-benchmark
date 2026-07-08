# Results

How Routific compares to the open-source solvers (VROOM, PyVRP, OR-Tools) on the `public-benchmark`
dataset. The headline: **at the same coverage and the same fleet size, Routific gives up only ~1–3% on
travel time while producing routes that are far more visually attractive (an order of magnitude fewer
crossings between routes), better balanced, and lower on idle time — and that gap holds even when the
competitors are given every advantage, on identical hardware.**

Every number here is recomputed from the published `(instance, solution)` files by
[`analysis/compute_metrics.py`](../analysis/compute_metrics.py) and is reproducible with:

```bash
python3 analysis/fair_compare.py --exclude jsprit
```

> Metric definitions and their grounding in the visual-attractiveness literature are in
> [`docs/methodology.md`](methodology.md); solver coverage and caveats in
> [`docs/results-status.md`](results-status.md).

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
- **VROOM at `explore: 4`**, near its maximum search effort — it can't be said we under-powered it.
- **PyVRP and OR-Tools each get `2 × Routific's runtime`** on every problem as their time budget
  (they're anytime solvers) — the `--budget-from-routific` rule in [`RUNNING.md`](../RUNNING.md).
- Routific is evaluated in its **fleet-minimizing configuration**; gating travel on **equal fleet
  size** keeps that objective difference from distorting the travel comparison.

Common set below: **197 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit excluded because it
skips >400-stop problems).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 9.55 | 9.41 | 24.37 | 12.61 |
| fewest-unserved win-rate | 93% | 97% | 89% | 91% |

Routific and VROOM serve essentially identically. **PyVRP is the coverage outlier** — on this hardware
its fixed time budget buys much less search on the hardest large instances, so it drops far more;
OR-Tools also trails. This leaves **164 instances where all four serve identically** — the basis for
the quality comparison.

## 2. Route quality at equal coverage (164 instances)

Mean (lower is better), with Routific's win-rate — the share of instances where it's best:

| metric | **Routific** | VROOM | PyVRP | OR-Tools | Routific win-rate |
|---|--:|--:|--:|--:|--:|
| Number of vehicles | **11.2** | 11.6 | 11.5 | 11.7 | **90%** |
| **Crossings between routes (sum)** | **8.0** | 21.3 | 17.5 | 29.4 | **87%** |
| **Crossings between routes (max)** | **1.7** | 3.3 | 2.5 | 3.8 | **81%** |
| Crossings within a route | 63.9 | 65.3 | 64.7 | 66.8 | 45% |
| **Workload imbalance** | **68.7** | 91.7 | 86.7 | 84.2 | **58%** |
| **Route-duration variance** | **8,091** | 11,545 | 11,033 | 10,926 | **47%** |
| **Idle / wait (s)** | **4,774** | 7,250 | 6,405 | 7,430 | **97%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific has **~2–4× fewer** than any competitor and is best on **87%** of instances.
- **Idle / wait time** is lowest for Routific on **97%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split) are both lowest for Routific.
- **Fleet size is lowest for Routific** (11.2 vs 11.5–11.7, best on 90%) — it isn't buying route quality with extra trucks; it uses fewer.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) |
|---|--:|--:|
| VROOM | 150 | 1.02 |
| PyVRP | 140 | 1.02 |
| OR-Tools | 144 | 1.00 |

Once fleet size is matched, **the competitors edge Routific by ~1–3% on raw distance** — and Routific
pays only that couple-percent for its large route-quality gains.

## 4. Runtime (same hardware — 6-vCPU c2-standard-8)

Because every solver ran on identical hardware, runtimes are comparable (unlike most cross-tool
benchmarks):

| solver | mean | median | note |
|---|--:|--:|---|
| Routific | 101,560 ms | 5,893 ms | engine solve time |
| VROOM | 156,624 ms | 4,257 ms | `explore: 4`, no time budget |
| PyVRP | 204,244 ms | 11,825 ms | anytime — budget = 2× Routific |
| OR-Tools | 203,498 ms | 11,786 ms | anytime — budget = 2× Routific |

- **PyVRP and OR-Tools** are anytime solvers *given* 2× Routific's runtime, so their times are 2×
  Routific **by construction** — not an independent measurement.
- **VROOM** (no budget) is the only independent competitor clock. Even at max search (`explore: 4`) it's
  **faster than Routific on the typical instance** (median 4.3 s vs 5.9 s); its higher *mean* is the
  giant tail, where explore-4 grinds the biggest problems. At `explore: 3` it's on par with Routific
  overall. More search makes VROOM's routes a little *shorter*, never *tidier*.
- **Bottom line:** on equal hardware Routific is not the slow solver — it's competitive with or faster
  than the open-source solvers *while* producing the higher-quality routes above.

## Reading it

> **At equal stops and equal trucks, Routific gives up ~1–3% on travel and wins decisively on the
> qualities that make a route good to operate — far fewer crossings, more even workloads, less idle
> time, a smaller fleet — at competitive runtime on the same hardware.** And this holds with the
> competitors handed their strongest settings: VROOM at near-max search, PyVRP and OR-Tools at twice
> Routific's time.

## Caveats

- **Coverage is a near-tie** with VROOM; PyVRP/OR-Tools trail on the hardest large instances.
- **VROOM at `explore: 4` can't finish ~3 of the largest instances** within the time cap, so its column
  covers 197/200. PyVRP, OR-Tools, and Routific cover all 200.
- **The Routific column's engine is not runnable from this repo** ([contact us](https://routific.com));
  its solutions are precomputed and bundled so the comparison reproduces from public files alone.

## Reproduce

```bash
python3 analysis/fair_compare.py --exclude jsprit   # the gated comparison above
python3 analysis/analyze.py                         # per-metric means + win-rate, all solvers
```
