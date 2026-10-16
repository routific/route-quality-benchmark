# Results — Routific vs jsprit

jsprit is compared **separately** because it only runs the smaller problems: by default it skips any
instance with **more than ~400 stops** (it doesn't scale into a comparable time budget), so it can't
be part of the four-way common set in [`results.md`](results.md). On the **145 instances it does
solve** (all ≤ 400 stops; median 80 visits), the picture is one-sided: **Routific beats jsprit on every
axis — coverage, route quality, *and* travel time.**

Every number is recomputed from the published `(instance, solution)` files and is reproducible with:

```bash
python3 analysis/fair_compare.py --exclude vroom,pyvrp,ortools   # leaves routific + jsprit
```

The comparison is gated the same way as the main results (coverage → quality at equal coverage →
travel at equal fleet). jsprit is an anytime solver given the same `max(2 s, 2 × Routific's runtime)` budget rule as the
other competitors (computed from the July 2026 Routific column and published in
[`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv) — see the runtime note in
[`results.md`](results.md)); on these small instances that's mostly the 2-second floor.

## 1. Coverage (unserved stops) — 145 instances

| | Routific | jsprit |
|---|--:|--:|
| mean unserved | **4.07** | 6.75 |
| fewest-unserved win-rate | **99%** | 81% |

Routific serves more stops than jsprit. This leaves **116 instances where both serve identically** —
the basis for the quality comparison.

## 2. Route quality at equal coverage (116 instances)

Mean (lower is better), with Routific's win-rate. The between-routes metrics only apply to the 77
multi-route instances in the set:

| metric | **Routific** | jsprit | Routific win-rate |
|---|--:|--:|--:|
| Number of vehicles | **3.4** | 3.6 | **100%** |
| **Crossings between routes (sum)** | **0.5** | 14.4 | **100%** |
| **Crossings between routes (max)** | **0.4** | 3.5 | **100%** |
| Crossings within a route | **12.6** | 17.2 | 84% |
| **Workload imbalance** | **24.3** | 34.6 | **77%** |
| **Route-duration variance** | **7,817** | 13,468 | **66%** |
| **Idle / wait (s)** | **2,368** | 4,082 | **99%** |

Routific has **~30× fewer crossings between routes** than jsprit and is best on **100%** of instances
for that metric — jsprit produces markedly more tangled routes. Routific is also lower on idle time
(99%), workload imbalance, route-duration variance, and fleet size.

## 3. Travel time, at equal coverage *and* equal fleet (92 instances)

| Routific vs | instances | travel ratio (Routific ÷ jsprit) |
|---|--:|--:|
| jsprit | 92 | **0.90** |

Unlike VROOM / PyVRP / OR-Tools — where Routific is within ~±1–2% on travel — **against jsprit
Routific is ~10% *shorter*** on travel, and lower on **91 of 92** head-to-heads.

## Reading it

> On the small-to-medium problems jsprit can handle, **Routific is strictly better — fewer unserved
> stops, an order of magnitude fewer crossings, more even and less-idle routes, a smaller fleet, and
> ~10% less travel.** jsprit is not competitive on this dataset, and it can't run the large instances at
> all.

## Caveats

- **jsprit covers 145/264** — only the ≤ 400-stop instances. The largest problems (up to 3,000+ stops)
  are outside its scope entirely.
- **Runtime is not compared for jsprit.** Its reported time is client-side wall-clock (it includes the
  HTTP round-trip and jsprit caps by iteration count, not a single server-side clock), so it isn't
  comparable to the c2-standard-8 runtimes in [`results.md`](results.md).
