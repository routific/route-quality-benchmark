# Running the benchmark — end to end

This is the full walkthrough: from a fresh clone to a solver-vs-solver comparison table. Every
open-source competitor runs locally in Docker; you don't install any solver yourself.

> **Routific's own v3 engine is not runnable from this repo.** These steps reproduce the **competitor**
> results and the analysis. To reproduce the Routific numbers in an isolated environment,
> [contact Routific](https://routific.com).

---

## 1. Prerequisites

| Need | Why | Check |
|---|---|---|
| **Docker** + Compose v2 | every solver runs as a container | `docker version` and `docker compose version` |
| **Python 3.8+** | the runner + analyzer (standard library only — nothing to `pip install`) | `python3 --version` |
| **git** | to clone | `git --version` |
| ~2 GB free disk | solver images + the dataset | — |

Make sure the **Docker daemon is running** before you start.

## 2. Get the repo

```bash
git clone https://github.com/routific/route-quality-benchmark.git
cd route-quality-benchmark
```

The dataset is already included under `datasets/public-benchmark/` (200 instances, gzipped). Peek at one:

```bash
python3 -c "import json,gzip; d=json.load(gzip.open('datasets/public-benchmark/cvrp/pb-0002.json.gz','rb')); print(d['type'], len(d['visits']),'visits',len(d['vehicles']),'vehicles')"
```

## 3. Run everything (the one command)

`run_benchmark.py` brings each solver's Docker service up, solves the instances, writes a
[Standard Solution](docs/standard-io-contract.md) per run, and tears the service down.

```bash
# default: a 5-instance sample (one per VRP type), all four solvers
python3 run_benchmark.py
```

- First run **builds** the PyVRP / OR-Tools / jsprit images (a few minutes, cached afterwards) and
  **pulls** the VROOM image.
- Results land in **`results/<solver>/<instance>.json`**.

Useful options:

```bash
python3 run_benchmark.py --solvers vroom,pyvrp          # subset of solvers
python3 run_benchmark.py --instances pb-0064,pb-0149    # specific instances
python3 run_benchmark.py --sample 20                    # first 20 dataset instances
python3 run_benchmark.py --time-limit-ms 5000           # flat budget for the anytime solvers
python3 run_benchmark.py --keep-up                      # leave services running between runs
```

### Solve budgets (how the official comparison is run)

The anytime solvers (PyVRP, OR-Tools, jsprit) are given a **per-problem** budget, not a flat one, so
each competitor gets time proportional to how hard the problem is:

> **budget(problem) = max(2000 ms, 2 × Routific's runtime on that problem)**

Routific's per-problem runtime is published in the `results/routific/<instance>.json` files
(`runtime_ms`), so the budgets are **fully reproducible from public data** — nothing hidden:

```bash
python3 run_benchmark.py --sample 200 --budget-from-routific
```

`--budget-from-routific` reads each budget straight from the published Routific results, so anyone runs
the competitors under the exact same time budgets we did. (VROOM has no time budget — it uses a fixed
`explore` level — so the budget never applies to it.)

> **jsprit skips instances with >400 stops by default** (it doesn't scale past that in a comparable
> budget). Override with `--force` on the per-solver command if you really want it.

### Running a single solver by hand

Every solver also works standalone (see each `solvers/<solver>/README.md`):

```bash
cd solvers/vroom && docker compose up -d          # (--build for pyvrp/ortools/jsprit)
python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz    # -> results/vroom/pb-0187.json
docker compose down
```

## 4. Analyze

Once `results/` has solutions from ≥2 solvers, compare them. The analyzer recomputes every metric from
the `(instance, solution)` files alone:

```bash
python3 analysis/analyze.py
```

It prints a **per-metric mean** table and a **win-rate** table, and writes
`results/_analysis/comparison.csv` + `win_rate.csv`. Metric definitions are in
[`analysis/README.md`](analysis/README.md).

## 5. Read the output

```
results/
├── vroom/pb-0187.json          one Standard Solution per (solver, instance)
├── pyvrp/…  ortools/…  jsprit/…
└── _analysis/
    ├── comparison.csv          per-metric means, one column per solver
    └── win_rate.csv            % of instances each solver is best on
```

Each solution file is a [Standard Solution](docs/standard-io-contract.md): per-route ordered visit
indices + unserved + `runtime_ms`.

## 6. Full 200-instance run

```bash
python3 run_benchmark.py --sample 200 --time-limit-ms 5000
python3 analysis/analyze.py
```

Heads-up: the dataset includes very large instances (up to ~3,500 stops); those take real time on the
anytime solvers, and jsprit auto-skips the >400-stop ones. Start with the default sample first.

## What you get vs. what's deferred

- ✅ The four **competitors** run and are compared on the route-quality metrics.
- ⏳ **Routific column** — not runnable here; its published results are provisional until re-run on these
  exact instances ([contact us](https://routific.com)).
- ⏳ **Runtime comparison** — intentionally omitted (the solvers ran under different clocks / stopping
  rules); see [`analysis/README.md`](analysis/README.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | start Docker Desktop / the daemon |
| A solver's `run.py` errors with a connection refused | the service isn't up yet — `docker compose up -d` in that solver dir and retry |
| Port already in use (3030/5001/5002/8080) | stop the conflicting container, or edit the port in that solver's `docker-compose.yml` |
| PyVRP image build is slow on Apple Silicon | expected — there's no arm64 wheel, so it compiles from source once (cached afterwards) |
| `no instances common to all selected solvers` | run `run_benchmark.py` first so every selected solver has results |

## License & attribution

Code is Apache-2.0; the dataset is under `datasets/public-benchmark/LICENSE`; the travel-time matrices
require **"© OpenStreetMap contributors"** attribution. See [`NOTICE`](NOTICE) and
[`THIRD-PARTY.md`](THIRD-PARTY.md).
