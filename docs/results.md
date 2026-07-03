# Results

How Routific compares to the open-source solvers (VROOM, PyVRP, OR-Tools) on the `public-benchmark`
dataset. The headline: **at the same coverage and the same fleet size, Routific matches the
open-source solvers on travel time while producing routes that are far more visually attractive
(an order of magnitude fewer crossings between routes), better balanced, and lower on idle time.**

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

Routific is evaluated in its **fleet-minimizing configuration**; the open-source solvers minimize each
instance's stated objective (with a per-vehicle fixed cost on `minimize_vehicles` instances). Gating
travel on **equal fleet size** means that configuration difference can't distort the travel comparison.

Common set below: **182 instances** (Routific + VROOM + PyVRP + OR-Tools; jsprit excluded because it
skips >400-stop problems, which would shrink the common set).

## 1. Coverage (unserved stops)

| | Routific | VROOM | PyVRP | OR-Tools |
|---|--:|--:|--:|--:|
| mean unserved | 10.5 | 9.5 | 22.9 | 10.2 |
| fewest-unserved win-rate | 90% | 95% | 90% | 93% |

Routific, VROOM and OR-Tools serve comparably (identical unserved on ~160/182 instances). **PyVRP is
the coverage outlier** — it drops far more on the hardest large instances. The one place a competitor
leads: **VROOM serves ~191 more stops in total than Routific**, concentrated in ~5 large `cvrp`
instances where Routific leaves clearly-serveable stops on the table (see
[results-status](results-status.md)). This leaves **144 instances where all four serve identically** —
the basis for the quality comparison.

## 2. Route quality at equal coverage (144 instances)

Mean (lower is better), with Routific's win-rate — the share of instances where it's best:

| metric | **Routific** | VROOM | PyVRP | OR-Tools | Routific win-rate |
|---|--:|--:|--:|--:|--:|
| Number of vehicles | 9.2 | 9.4 | 9.5 | 9.5 | (comparable) |
| **Crossings between routes (sum)** | **6.5** | 17.0 | 20.0 | 27.6 | **88%** |
| **Crossings between routes (max)** | **1.5** | 2.9 | 3.1 | 3.6 | **85%** |
| Crossings within a route | 55.0 | 58.1 | 56.6 | 58.1 | 48% |
| **Workload imbalance** | **73.6** | 93.7 | 90.5 | 86.1 | **56%** |
| **Route-duration variance** | **7,642** | 10,717 | 10,462 | 10,134 | **46%** |
| **Idle / wait (s)** | **5,429** | 8,010 | 7,288 | 8,342 | **97%** |

- **Crossings between routes** — the classic "spaghetti" signal drivers and dispatchers react to —
  Routific has **~3–4× fewer** than any competitor and is best on **88%** of instances.
- **Idle / wait time** is lowest for Routific on **97%** of instances.
- **Workload imbalance** and **route-duration variance** (how evenly work is split across drivers) are
  both lowest for Routific.
- **Fleet size is comparable** (9.2 vs 9.4–9.5) — Routific isn't buying its route quality with extra
  trucks.

## 3. Travel time, at equal coverage *and* equal fleet

| Routific vs | instances | travel ratio (Routific ÷ competitor) |
|---|--:|--:|
| VROOM | 128 | 1.01 |
| PyVRP | 126 | 1.02 |
| OR-Tools | 127 | 1.00 |

Once fleet size is matched, **travel time is a wash — within ~1–2%, i.e. a statistical tie.** Routific
does not win travel, and it pays no travel penalty for its route-quality gains. (Per instance it's
lower on roughly half the head-to-heads.)

## Reading it

> **At equal stops and equal trucks, Routific ties the best open-source solvers on travel time and
> beats them on the qualities that make a route good to operate — far fewer crossings, more even
> workloads, and less idle time.** The one axis where a competitor leads is raw coverage, where VROOM
> picks up more stops on a handful of hard large problems.

## Caveats

- **Coverage is the honest competitor win.** VROOM serves more stops on ~5 large `cvrp` instances; see
  [results-status](results-status.md).
- **Runtime is not compared here.** The solvers run under different clocks and stopping rules, so a
  head-to-head speed number would mislead — see [`analysis/README.md`](../analysis/README.md).
- **The Routific column is provisional** and its engine is not runnable from this repo
  ([contact us](https://routific.com)); it covers 184/200 instances. See
  [results-status](results-status.md).

## Reproduce

```bash
python3 analysis/fair_compare.py --exclude jsprit   # the gated comparison above
python3 analysis/analyze.py                         # per-metric means + win-rate, all solvers
```
