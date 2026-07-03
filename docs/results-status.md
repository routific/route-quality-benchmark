# Results status

What's published under [`results/`](../results/), how complete each solver's coverage is, and the
caveats to read the numbers with. Each file is a [Standard Solution](standard-io-contract.md); the
analyzer recomputes every metric from `(instance, solution)`, so anyone can reproduce the tables.

## Coverage

The dataset has **200 instances**. Published coverage per solver:

| solver | results | notes |
|---|---:|---|
| **OR-Tools** | 200 / 200 | complete |
| **PyVRP** | 200 / 200 | complete (see repair note) |
| **VROOM** | 198 / 200 | missing `pb-0084`, `pb-0122` |
| **jsprit** | 126 / 200 | skips instances > 400 stops by default |
| **Routific** | 184 / 200 | published, **provisional** — engine not runnable from this repo |

The analyzer compares on the **intersection** of the selected solvers (instances all of them solved),
so a solver's gaps only shrink the common set for comparisons that include it — they don't corrupt
other solvers' numbers. Run `analysis/analyze.py --exclude jsprit` to compare over a larger common set.

## Per-solver notes

- **VROOM** runs at a fixed `explore` effort level and has **no time budget**, so it does not take the
  per-problem budget the anytime solvers do. It ran out of memory on two of the largest instances
  (`pb-0084`, `pb-0122`); those two are simply absent rather than reported as failures.
- **PyVRP** is a hard-constrained solver. On a few instances feasibility *requires* dropping stops (total
  demand exceeds fleet capacity, or shifts are too short to cover every stop). PyVRP can return an
  over-serving **infeasible** best there; the harness **repairs it to feasibility** by dropping the
  minimal set of violating stops per route (recorded as `meta.repaired` / `repaired_drops` in the
  solution). Without this, six instances would report every stop as unserved.
- **jsprit** auto-skips instances above 400 stops (it doesn't scale into a comparable budget); override
  with `--force` on its harness if you want to run them anyway.
- **OR-Tools** and **PyVRP** cover the full 200 including the largest (3,000+ stop) instances.

## Solve budgets

The anytime solvers (PyVRP, OR-Tools, jsprit) are given a **per-problem** budget, not a flat one:

> **budget(problem) = max(2000 ms, 2 × Routific's runtime on that problem)**

Routific's per-problem runtime is published in the `results/routific/*.json` files, so the budgets are
**fully reproducible from public data** — `run_benchmark.py --budget-from-routific` reads them
straight from those files. VROOM has no budget (fixed effort). See the Solve-budgets section of
[`RUNNING.md`](../RUNNING.md).

## Caveats

- **The Routific column is provisional.** Routific's engine is not runnable from this repo, so its
  results are precomputed and bundled. The exact engine configuration used for the published run is
  still being finalized; treat the Routific numbers as indicative until this note is updated. To
  reproduce them in an isolated environment, [contact Routific](https://routific.com).
- **Runtime is not compared** — the solvers ran under different clocks and stopping rules. See
  [`analysis/README.md`](../analysis/README.md#caveats).
- **Some instances have unavoidable unserved stops** (tight windows / capacity). "Unserved" is a
  reported quantity per solution, not an error; the analyzer accounts for it.
