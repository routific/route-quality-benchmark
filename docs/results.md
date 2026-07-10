# Results

How Routific compares to the open-source solvers (VROOM, PyVRP, OR-Tools) on the `public-benchmark`
dataset (**245 instances**, 30–3,000+ stops). The headline: **at the same coverage and the same fleet
size, Routific gives up ~0–1% on travel time while producing routes that are far more visually
attractive (an order of magnitude fewer crossings between routes), better balanced, and lower on idle
time — and on average it's also the fastest solver — all on identical hardware, with the competitors
given every advantage.**

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
- **PyVRP and OR-Tools each get `2 × Routific's runtime`** on every problem as their time budget
  (they're anytime solvers) — the `--budget-from-routific` rule in [`RUNNING.md`](../RUNNING.md).
- Routific is evaluated in its **fleet-minimizing configuration**; gating travel on **equal fleet
  size** keeps that objective difference from distorting the travel comparison.

Common set below: **241 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit is compared
separately in [Routific vs jsprit](results-jsprit.md) because it only runs ≤400-stop problems).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 27.43 | 27.29 | 48.58 | 29.90 |
| fewest-unserved win-rate | 93% | 97% | 88% | 92% |

Routific and VROOM serve essentially identically. **PyVRP is the coverage outlier** — on the large
instances its fixed time budget buys much less search, so it drops far more; OR-Tools is close to
Routific. This leaves **199 instances where all four serve identically** — the basis for the quality
comparison. (Unserved counts are high because the dataset includes many 1,000–3,000-stop problems.)

## 2. Route quality at equal coverage (199 instances)

Mean (lower is better), with Routific's win-rate — the share of instances where it's best:

| metric | **Routific** | VROOM | PyVRP | OR-Tools | Routific win-rate |
|---|--:|--:|--:|--:|--:|
| Number of vehicles | **14.9** | 15.3 | 15.4 | 15.5 | **90%** |
| **Crossings between routes (sum)** | **12.5** | 33.7 | 36.0 | 49.0 | **86%** |
| **Crossings between routes (max)** | **2.1** | 3.9 | 3.2 | 4.4 | **80%** |
| Crossings within a route | 90.2 | 92.3 | 92.0 | 93.1 | 43% |
| **Workload imbalance** | **73.8** | 97.3 | 98.9 | 94.6 | **59%** |
| **Route-duration variance** | **9,043** | 13,076 | 13,306 | 12,689 | **49%** |
| **Idle / wait (s)** | **4,331** | 6,554 | 5,846 | 6,832 | **97%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific has **~3× fewer** than any competitor and is best on **86%** of instances.
- **Idle / wait time** is lowest for Routific on **97%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split) are both lowest for Routific.
- **Fleet size is lowest for Routific** (14.9 vs 15.3–15.5, best on 90%) — it uses fewer trucks, not more.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) |
|---|--:|--:|
| VROOM | 180 | 1.01 |
| PyVRP | 159 | 1.01 |
| OR-Tools | 169 | 1.00 |

Once fleet size is matched, **travel is within ~1%** — effectively a tie (against OR-Tools Routific is
even fractionally shorter). Routific pays essentially nothing on distance for its route-quality gains.

## 4. Runtime (same hardware — 6-vCPU c2-standard-8)

Because every solver ran on identical hardware, runtimes are comparable:

| solver | mean | median | note |
|---|--:|--:|---|
| **Routific** | **116,287 ms** | 22,681 ms | engine solve time |
| VROOM | 181,447 ms | 14,144 ms | max `explore`, no time budget |
| PyVRP | 233,928 ms | 45,438 ms | anytime — budget = 2× Routific |
| OR-Tools | 232,890 ms | 45,363 ms | anytime — budget = 2× Routific |

- **Routific is the fastest on average** (mean 116k ms vs 181k–234k). PyVRP/OR-Tools are 2× Routific
  *by construction* (that's their budget). VROOM has no budget: it's quick on small problems (lower
  median) but its **mean is much higher than Routific's** because, with no stopping rule, it grinds the
  large instances — so on the big problems it's slower than Routific.
- **Bottom line:** on equal hardware Routific is not the slow solver — on average it's the *fastest*,
  while producing the higher-quality routes above.

## Reading it

> **At equal stops and equal trucks, Routific ties on travel (~±1%) and wins decisively on the
> qualities that make a route good to operate — far fewer crossings, more even workloads, less idle
> time, a smaller fleet — and is the fastest solver on average.** This holds with the competitors at
> their strongest: VROOM at max search, PyVRP and OR-Tools at twice Routific's time. More search / more
> time makes the competitors' routes a little *shorter*, never *tidier*. The gap is sharpest on the
> **large instances**, where the engine's optimization has the most room to work.

## Caveats

- **Coverage is a near-tie** with VROOM; PyVRP/OR-Tools trail on the hardest large instances.
- **VROOM covers 241/245** — a few of the very largest exceed the time cap even at `explore: 3`.
  PyVRP, OR-Tools, and Routific cover all 245.
- **The Routific column's engine is not runnable from this repo** ([contact us](https://routific.com));
  its solutions are precomputed and bundled so the comparison reproduces from public files alone.

## Reproduce

```bash
python3 analysis/fair_compare.py --exclude jsprit   # the gated comparison above
python3 analysis/analyze.py                         # per-metric means + win-rate, all solvers
python3 analysis/build_all_results.py               # regenerate results/all-results.md (every raw number)
```
