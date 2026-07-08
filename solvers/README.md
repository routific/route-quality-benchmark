# Solver harnesses

Each competitor solver is packaged so it runs on a fresh machine via Docker and speaks the
[Standard I/O contract](../docs/standard-io-contract.md): it takes a **Standard Instance** and produces
a **Standard Solution** (a per-route ordered permutation of visit indices). This lets every solver be
compared head-to-head on the same problems, and lets the [analyzer](../analysis/) recompute every
metric from `(instance, solution)` alone.

> Routific's own v3 engine is **not** runnable from this repo — [contact Routific](https://routific.com).
> Its results are published so the comparison is complete.

## Running a solver

Bring the solver's service up once, then solve any number of instances against it:

```bash
cd solvers/vroom && docker compose up -d          # (--build for pyvrp/ortools/jsprit)
python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz
```

**Interface (uniform across solvers):**

```
solvers/<solver>/run.py  <instance.json[.gz]>  [-o out.json]
      → reads a Standard Instance, solves it, writes a Standard Solution
```

**Output location.** By default the solution is written to **`results/<solver>/<instance>.json`** at the
repo root (override with `-o`). e.g. the command above writes `results/vroom/pb-0187.json`. Under
`results/`, only the published solver columns are tracked in git; everything else there (experiments,
variants, generated tables) is git-ignored local run artifacts.

**jsprit scale cap.** `solvers/jsprit/run.py` **skips instances with >400 stops by default** (jsprit
doesn't scale past that in a comparable budget); pass `--force` (or `--max-stops N`) to override.

All solvers run in **custom-matrix mode**: the request carries the instance's raw-OSRM `distances`
matrix, so there is no OSRM/map backend — the comparison isolates routing-algorithm quality from ETA
methodology.

| solver | engine | how it runs | port |
|---|---|---|---|
| [`vroom/`](vroom/)   | VROOM (C++)            | prebuilt image, HTTP service | 3030 |
| `pyvrp/`   | PyVRP (HGS, Python)    | built image, HTTP service | 5002 |
| `ortools/` | Google OR-Tools        | built image, HTTP service | 5001 |
| `jsprit/`  | jsprit (Java)          | built image, HTTP service | 8080 |

## Shared code

- [`common/standard_io.py`](common/standard_io.py) — load a Standard Instance (`.json`/`.json.gz`),
  write a Standard Solution, and coverage-check a solution against its instance.

## Modeling notes (all solvers)

The Standard Instance is already the **hard-constrained** form (soft `etas_options` removed at export),
so nothing is skipped for soft constraints.

**`minimize_vehicles`.** When the instance sets it, each solver charges a **fixed cost per vehicle
used**, calibrated to sit *just below the value of serving a visit* — so the solver consolidates routes
but never drops a servable stop to save a vehicle. The hierarchy is **serve > minimize vehicles >
minimize travel time**. Per solver: VROOM `costs.fixed`; PyVRP `fixed_cost` < serve-prize; OR-Tools
fixed cost < drop penalty; JSprit per-vehicle fixed cost < unassigned penalty.

Work-balance and other Routific-specific objectives are not modeled by the open-source solvers.
Per-solver specifics are in each solver's README.

## Licensing

Each solver is third-party open source under its own upstream license and is pulled/built at runtime,
not redistributed here. See [`../THIRD-PARTY.md`](../THIRD-PARTY.md). The adapter/harness code in this
repo is Apache-2.0.
