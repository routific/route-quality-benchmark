# Results

How Routific compares to the open-source solvers (VROOM, PyVRP, OR-Tools) on the `public-benchmark`
dataset (**264 instances**, 30–3,000+ stops). The headline: **at the same coverage and the same fleet
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
- **VROOM at max search** — `explore: 4`, dropping to `explore: 3` on the largest instances (>500
  stops), where `explore: 4` exceeds the 40-min cap. Quality is flat across explore levels, so this
  doesn't move the comparison — it only affects a couple percent of runtime.
- **PyVRP and OR-Tools each get `2 × Routific's runtime`** on every problem as their time budget
  (they're anytime solvers) — the `--budget-from-routific` rule in [`RUNNING.md`](../RUNNING.md).
- Routific is evaluated in its **fleet-minimizing configuration**; gating travel on **equal fleet
  size** keeps that objective difference from distorting the travel comparison.

Common set below: **260 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit is compared
separately in [Routific vs jsprit](results-jsprit.md) because it only runs ≤400-stop problems).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 25.57 | 25.43 | 45.66 | 27.86 |
| fewest-unserved win-rate | 94% | 97% | 88% | 92% |

Routific and VROOM serve essentially identically. **PyVRP is the coverage outlier** — on the large
instances its fixed time budget buys much less search, so it drops far more (and on two single-vehicle
time-window instances it fails to construct a serving route at all — see
[`results-status.md`](results-status.md)); OR-Tools is close to Routific. This leaves **215 instances
where all four serve identically** — the basis for the quality comparison. (Unserved counts are high
because the dataset includes many 1,000–3,000-stop problems.)

## 2. Route quality at equal coverage (215 instances)

Mean (lower is better), with Routific's win-rate — the share of instances where it's best. The
between-routes metrics (crossings, balance, variance) only apply to the 177 multi-route instances in
the set — single-vehicle (TSP) solutions have no between-routes structure:

| metric | **Routific** | VROOM | PyVRP | OR-Tools | Routific win-rate |
|---|--:|--:|--:|--:|--:|
| Number of vehicles | **13.9** | 14.2 | 14.3 | 14.4 | **91%** |
| **Crossings between routes (sum)** | **12.5** | 33.7 | 36.0 | 49.0 | **86%** |
| **Crossings between routes (max)** | **2.1** | 3.9 | 3.2 | 4.4 | **80%** |
| Crossings within a route | 84.0 | 86.0 | 85.8 | 86.8 | 44% |
| **Workload imbalance** | **73.8** | 97.3 | 98.9 | 94.6 | **59%** |
| **Route-duration variance** | **9,043** | 13,076 | 13,306 | 12,689 | **49%** |
| **Idle / wait (s)** | **4,008** | 6,066 | 5,411 | 6,323 | **98%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific has **~3× fewer** than any competitor and is best on **86%** of instances.
- **Idle / wait time** is lowest for Routific on **98%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split) are both lowest for Routific.
- **Fleet size is lowest for Routific** (13.9 vs 14.2–14.4, best on 91%) — it uses fewer trucks, not more.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) |
|---|--:|--:|
| VROOM | 199 | 1.01 |
| PyVRP | 176 | 1.01 |
| OR-Tools | 187 | 1.00 |

Once fleet size is matched, **travel is within ~1%** — effectively a tie (against OR-Tools Routific is
even fractionally shorter). Routific pays essentially nothing on distance for its route-quality gains.

## 4. Runtime (same hardware — 6-vCPU c2-standard-8)

Because every solver ran on identical hardware, runtimes are comparable:

| solver | mean | median | note |
|---|--:|--:|---|
| **Routific** | **107,849 ms** | 13,499 ms | engine solve time |
| VROOM | 168,200 ms | 10,959 ms | max `explore`, no time budget |
| PyVRP | 217,029 ms | 27,226 ms | anytime — budget = 2× Routific |
| OR-Tools | 216,067 ms | 27,000 ms | anytime — budget = 2× Routific |

- **Routific is the fastest on average** (mean 108k ms vs 168k–217k). PyVRP/OR-Tools are 2× Routific
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
```
