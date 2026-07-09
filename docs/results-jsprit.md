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
travel at equal fleet). jsprit is an anytime solver given the same `2 × Routific's runtime` budget as
the other competitors; on these small instances that's mostly the 2-second floor.

## 1. Coverage (unserved stops) — 145 instances

| | Routific | jsprit |
|---|--:|--:|
| mean unserved | **4.03** | 6.75 |
| fewest-unserved win-rate | **100%** | 81% |

Routific serves more stops than jsprit. This leaves **117 instances where both serve identically** —
the basis for the quality comparison.

## 2. Route quality at equal coverage (117 instances)

Mean (lower is better), with Routific's win-rate. The between-routes metrics only apply to the 78
multi-route instances in the set:

| metric | **Routific** | jsprit | Routific win-rate |
|---|--:|--:|--:|
| Number of vehicles | **3.5** | 3.7 | **100%** |
| **Crossings between routes (sum)** | **1.1** | 14.4 | **100%** |
| **Crossings between routes (max)** | **0.6** | 3.5 | **99%** |
| Crossings within a route | **12.8** | 17.1 | 78% |
| **Workload imbalance** | **24.9** | 34.9 | **78%** |
| **Route-duration variance** | **7,775** | 13,922 | **71%** |
| **Idle / wait (s)** | **2,355** | 4,047 | **99%** |

Routific has **~13× fewer crossings between routes** than jsprit and is best on **100%** of instances
for that metric — jsprit produces markedly more tangled routes. Routific is also lower on idle time
(99%), workload imbalance, route-duration variance, and fleet size.

## 3. Travel time, at equal coverage *and* equal fleet (95 instances)

| Routific vs | instances | travel ratio (Routific ÷ jsprit) |
|---|--:|--:|
| jsprit | 95 | **0.91** |

Unlike VROOM / PyVRP / OR-Tools — where Routific ties or gives up ~1% on travel — **against jsprit
Routific is ~9% *shorter*** on travel, and lower on **93 of 95** head-to-heads.

## Reading it

> On the small-to-medium problems jsprit can handle, **Routific is strictly better — fewer unserved
> stops, an order of magnitude fewer crossings, more even and less-idle routes, a smaller fleet, and
> ~9% less travel.** jsprit is not competitive on this dataset, and it can't run the large instances at
> all.

## Caveats

- **jsprit covers 145/264** — only the ≤ 400-stop instances. The largest problems (up to 3,000+ stops)
  are outside its scope entirely.
- **Runtime is not compared for jsprit.** Its reported time is client-side wall-clock (it includes the
  HTTP round-trip and jsprit caps by iteration count, not a single server-side clock), so it isn't
  comparable to the c2-standard-8 runtimes in [`results.md`](results.md).
