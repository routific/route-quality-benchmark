# Results status

What's published under [`results/`](../results/), how complete each solver's coverage is, and the
caveats to read the numbers with. Each file is a [Standard Solution](standard-io-contract.md); the
analyzer recomputes every metric from `(instance, solution)`, so anyone can reproduce the tables.

## Coverage

The dataset has **264 instances**. Published coverage per solver:

| solver | results | notes |
|---|---:|---|
| **Routific** | 264 / 264 | complete — engine not runnable from this repo, solutions bundled |
| **OR-Tools** | 264 / 264 | complete |
| **PyVRP** | 264 / 264 | complete (see repair note) |
| **VROOM** | 260 / 264 | a few of the very largest exceed the time cap (see note) |
| **jsprit** | 145 / 264 | skips instances > 400 stops by default |

The analyzer compares on the **intersection** of the selected solvers (instances all of them solved),
so a solver's gaps only shrink the common set for comparisons that include it — they don't corrupt
other solvers' numbers. Run `analysis/analyze.py --exclude jsprit` to compare over a larger common set.

## Per-solver notes

- **VROOM** runs at a fixed `explore` search level and has **no time budget**. It's published at max
  search — `explore: 4`, dropping to `explore: 3` on the largest instances (>500 stops), where
  `explore: 4` exceeds the 40-min per-request cap. Quality is flat across explore levels, so this only
  affects a couple percent of runtime, not the comparison. A few of the very largest instances exceed
  the cap even at `explore: 3` and are simply absent rather than reported as failures.
- **PyVRP** is a hard-constrained solver. On a few instances feasibility *requires* dropping stops (total
  demand exceeds fleet capacity, or shifts are too short to cover every stop). PyVRP can return an
  over-serving **infeasible** best there; the harness **repairs it to feasibility** by dropping the
  minimal set of violating stops per route (recorded as `meta.repaired` / `repaired_drops` in the
  solution). Without this, six instances would report every stop as unserved.
- **PyVRP fails to construct a serving route on two single-vehicle time-window instances**
  (`pb-0252`, `pb-0263`) even at its full budget — it treats time windows as hard, and with one
  vehicle there is no route-splitting recourse, so it returns a route serving only a handful of
  stops. This is a solver limitation, not a budget artifact (the result is identical at 2 s, at the
  July budget and at the current 2× budget).
- **jsprit** auto-skips instances above 400 stops (it doesn't scale into a comparable budget); override
  with `--force` on its harness if you want to run them anyway.
- **OR-Tools** and **PyVRP** cover the full 264 including the largest (3,000+ stop) instances.

## The Routific column

`results/routific/` is the per-instance **best-of** two engine runs over all 264 instances, picked by
the objective hierarchy serve → vehicles → travel time (`meta.best_of` in each file records which):

| component | solver | hardware | benchmark run | instances |
|---|---|---|---|--:|
| LS | local-search VRP | CPU | 2487 | 264 / 264 |
| GA | genetic algorithm | GPU | 2486 | 258 / 264 |

- Both runs: engine branch `force-min-vehicles` (develop `587b94e2` + `minimize_vehicles` forced on —
  the fleet-minimizing configuration), 2026-10-15.
- **Split:** GA is the best-of on 212 instances, LS on 52.
- **The GA run skips the 6 single-vehicle TSPs `pb-0259`..`pb-0264`**, so those use the LS solution
  directly (`meta.only = "ls"`).
- Coverage: 264 / 264 instances have a solution.

### What changed vs the previous column

The previous `results/routific/` (July 2026) was a best-of of earlier engine runs (96 LS / 168 GA).
Totals of Routific against itself over all 264 instances (lower is better for every metric):

| metric | previous | current | change |
|---|--:|--:|--:|
| Total travel time (s) | 35,992,671 | 35,208,717 | −2.2% |
| Crossings between routes (sum) | 2,691 | 1,043 | **−61.2%** |
| Crossings between routes (max) | 461 | 315 | −31.7% |
| Crossings within a route | 22,275 | 21,930 | −1.5% |
| Workload imbalance | 15,880 | 15,913 | +0.2% |
| Route-duration variance | 2,135,383 | 2,027,655 | −5.0% |
| Idle / wait (s) | 1,078,352 | 1,056,876 | −2.0% |
| Unserved stops | 7,327 | 7,301 | −0.4% |
| Vehicles | 4,246 | 4,236 | −0.2% |
| **Runtime (ms)** | 30,649,370 | 43,620,701 | **+42.3%** |

The quality gains (most visibly crossings between routes) come with a **~42% higher total runtime**
(mean 116,096 → 165,230 ms per instance; median 14,992 → 22,688 ms). Because the competitor budgets
are 2× Routific's runtime, PyVRP and OR-Tools were then rerun against this column in October 2026 (see
[Solve budgets](#solve-budgets)); the current four-solver numbers are in [`results.md`](results.md).

## Solve budgets

The anytime solvers (PyVRP, OR-Tools, jsprit) are given a fixed **per-problem** budget, proportionate
to problem difficulty, not a flat one:

> **budget(problem) = max(2000 ms, 2 × the current Routific runtime on that problem)**

PyVRP and OR-Tools were rerun at these budgets in October 2026, on the same `c2-standard-8` pool, after
the Routific column was refreshed. The only exception is the two largest instances, `pb-0089` and
`pb-0102`, which keep their July solutions, run at 2× the **July** Routific runtime (0.54 h and 0.77 h —
about 0.8× the current Routific runtime on those two). Every per-problem budget is published in
[`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv) (`pb_name`, `budget_ms`, the
Routific runtime it was computed from, and `source`: `2x-routific-oct2026`, or `2x-routific-jul2026` for
the two exceptions), and `run_benchmark.py --budget-map results/competitor-budgets.tsv` re-runs the
competitors at exactly those budgets. Over all 264 problems the budgets total 1.84× the current Routific
runtime (2× everywhere except the two exceptions).

The reported runtimes sit at their budgets: OR-Tools within 0.3% on every instance, PyVRP within 2.5% on
every instance but one — PyVRP's reported runtime includes its post-solve repair of dropped visits, so
on `pb-0240` (1,925 dropped, then 900 repaired) it exceeds the budget by about 5%.

jsprit was **not** rerun: its column is still the July run, at `max(2000 ms, 2 ×` the July Routific
runtime`)` — on its ≤400-stop instances about half are at the 2-second floor — so its budgets are not the ones in
the table above. VROOM has no budget (fixed effort). See the Solve-budgets section of
[`RUNNING.md`](../RUNNING.md).

## Caveats

- **The Routific column** is the engine run in its **fleet-minimizing configuration** (it minimizes
  the number of vehicles), best-of its two solvers per instance — details in
  [the Routific column](#the-routific-column). It's precomputed and bundled because the engine isn't
  runnable from this repo; to reproduce it in an isolated environment, [contact Routific](https://routific.com).
- **Coverage is a near-tie** between Routific and VROOM (mean unserved 25.47 vs 25.43 on the common set);
  PyVRP and OR-Tools trail on the hardest large instances. See [`docs/results.md`](results.md).
- **Runtime IS compared** — every solver ran on identical hardware (6-vCPU `c2-standard-8`), so runtimes
  are directly comparable; see the Runtime section of [`docs/results.md`](results.md).
- **Some instances have unavoidable unserved stops** (tight windows / capacity). "Unserved" is a
  reported quantity per solution, not an error; the analyzer accounts for it. The extreme case is
  `pb-0264`: its windows can't be met by a single vehicle under the hard-constrained contract, so
  every solver leaves essentially all of its stops unserved.
