# Results status

What's published under [`results/`](../results/), how complete each solver's coverage is, and the
caveats to read the numbers with. Each file is a [Standard Solution](standard-io-contract.md); the
analyzer recomputes every metric from `(instance, solution)`, so anyone can reproduce the tables.

## Coverage

The dataset has **264 instances**. Published coverage per solver:

| solver | results | notes |
|---|---:|---|
| **Routific** | 264 / 264 | complete — engine not runnable from this repo, solutions bundled |
| **PyVRP, OR-Tools** | 264 / 264 | complete (PyVRP: see the repair note) |
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
  minimal set of violating stops per route (recorded as `meta.repaired_drops` in the
  solution). In the published column, 14 instances carry a repair (`meta.repaired_drops` > 0).
- **PyVRP fails to construct a serving route on two single-vehicle time-window instances**
  (`pb-0252`, `pb-0263`) even at its full budget — it treats time windows as hard, and with one
  vehicle there is no route-splitting recourse, so it returns a route serving only a handful of
  stops. This is a solver limitation, not a budget artifact (the result is identical at 2 s and at
  the full 2× budget).
- **jsprit** auto-skips instances above 400 stops (it doesn't scale into a comparable budget); override
  with `--force` on its harness if you want to run them anyway.

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

## Solve budgets

The anytime solvers (PyVRP, OR-Tools, jsprit) are given a fixed **per-problem** budget, proportionate
to problem difficulty, not a flat one:

> **budget(problem) = max(2000 ms, 2 × Routific's runtime on that problem)**

Every per-problem budget is published in
[`results/competitor-budgets.tsv`](../results/competitor-budgets.tsv) (`pb_name`, `budget_ms`, and the
Routific runtime it was computed from), and `run_benchmark.py --sample 264 --budget-map
results/competitor-budgets.tsv` re-runs the competitors at exactly those budgets. PyVRP and OR-Tools
ran on `c2-standard-8` nodes from the same pool, one solve per node; the published columns were
produced on 2026-10-16. The reported runtimes include the solver's model build and PyVRP's post-solve repair, so they can sit slightly above the budget. jsprit, compared separately, was run at 2× the
runtime of the Routific column current at the time of its run (on its ≤400-stop instances mostly the
2-second floor); the budgets in the table apply to PyVRP and OR-Tools. VROOM has no budget (fixed effort).
See the Solve-budgets section of [`RUNNING.md`](../RUNNING.md).

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
