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
  stops. This is a solver limitation, not a budget artifact (the result is identical at 2 s and at
  the full 2× budget).
- **jsprit** auto-skips instances above 400 stops (it doesn't scale into a comparable budget); override
  with `--force` on its harness if you want to run them anyway.
- **OR-Tools** and **PyVRP** cover the full 264 including the largest (3,000+ stop) instances.

## Solve budgets

The anytime solvers (PyVRP, OR-Tools, jsprit) are given a **per-problem** budget, not a flat one:

> **budget(problem) = max(2000 ms, 2 × Routific's runtime on that problem)**

Routific's per-problem runtime is published in the `results/routific/*.json` files, so the budgets are
**fully reproducible from public data** — `run_benchmark.py --budget-from-routific` reads them
straight from those files. VROOM has no budget (fixed effort). See the Solve-budgets section of
[`RUNNING.md`](../RUNNING.md).

## Caveats

- **The Routific column** is the engine run in its **fleet-minimizing configuration** (it minimizes
  the number of vehicles), best-of its two solvers per instance. It covers all 264 instances. (On the
  19 single-vehicle instances added 2026-07-08, the GA component completed only 13 — the remaining 6
  use the LS solution directly.) It's precomputed and bundled because the engine isn't runnable from
  this repo; to reproduce it in an isolated environment, [contact Routific](https://routific.com).
- **Coverage is a near-tie** between Routific and VROOM (mean unserved 25.57 vs 25.43 on the common set);
  PyVRP and OR-Tools trail on the hardest large instances. See [`docs/results.md`](results.md).
- **Runtime IS compared** — every solver ran on identical hardware (6-vCPU `c2-standard-8`), so runtimes
  are directly comparable; see the Runtime section of [`docs/results.md`](results.md).
- **Some instances have unavoidable unserved stops** (tight windows / capacity). "Unserved" is a
  reported quantity per solution, not an error; the analyzer accounts for it. The extreme case is
  `pb-0264`: its windows can't be met by a single vehicle under the hard-constrained contract, so
  every solver leaves essentially all of its stops unserved.
