# Routing Quality Benchmark

An open, **reproducible** benchmark comparing vehicle-routing (VRP) solvers on real-world,
anonymized delivery problems — measuring not just total travel time, but the qualities that make a
route *good to drive*: compactness, non-overlapping/non-crossing routes, balanced workloads, and
fleet utilization.

> **Status.** Complete end to end: the standard data contract, the published `public-benchmark`
> dataset, the Dockerized solver harnesses, the batch runner, and the analyzer. See
> [`docs/methodology.md`](docs/methodology.md) for how the datasets and metrics were built, and
> [`docs/results-status.md`](docs/results-status.md) for what's published and the known gaps.

## What's here

| Path | What it is |
|---|---|
| [`docs/standard-io-contract.md`](docs/standard-io-contract.md) | **The foundation** — the Standard Instance & Standard Solution formats every dataset/solver/metric conforms to. |
| [`schema/`](schema/) | JSON Schemas + worked examples for the contract. |
| [`datasets/`](datasets/) | Published benchmark datasets as plain files. |
| [`solvers/`](solvers/) | Dockerized open-source solver harnesses (VROOM, PyVRP, OR-Tools, jsprit). |
| `run_benchmark.py` | One-command batch runner (all solvers over a set of instances). |
| [`analysis/`](analysis/) | The comparison analyzer + metric definitions. |
| [`results/`](results/) | Published solver results (the four competitors + Routific's); re-runs and analysis output land here too. |
| [`results/all-results.md`](results/all-results.md) | **Every raw number in one table** — one row per instance, all metrics × all solvers. |
| [`RUNNING.md`](RUNNING.md) | **Step-by-step guide** to run the solvers + analysis end to end. |
| [`docs/results.md`](docs/results.md) | **The findings** — Routific vs. the open-source solvers, compared fairly (equal coverage, equal fleet). |
| [`docs/methodology.md`](docs/methodology.md) | How the dataset was built (anonymization, selection) and why the metrics were chosen. |
| `tools/vrp_classify.py` | Classifies a Standard Instance by VRP type (TSP/CVRP/VRPTW/…). |

## Quickstart

**Full step-by-step walkthrough: [`RUNNING.md`](RUNNING.md)** — prerequisites, running every solver, and
the analysis. In short (needs Docker + Python 3; the runner and analyzer use only the standard library):

```bash
python3 run_benchmark.py        # run the 4 solvers on a 5-instance sample -> results/<solver>/…
python3 analysis/analyze.py     # compare them -> results/_analysis/*.csv
```

Or run a single solver by hand (see [`solvers/README.md`](solvers/README.md)):

```bash
cd solvers/vroom && docker compose up -d
python3 run.py ../../datasets/public-benchmark/tsp/pb-0187.json.gz   # -> results/vroom/pb-0187.json
```

## Reproducibility model

- **Datasets ship as files.** Every problem instance — including its pre-computed **raw-OSRM**
  travel-time matrix — is committed, so results don't depend on any hosted service.
- **Solvers run locally via Docker.** Each open-source competitor is packaged so it runs on a fresh
  machine and speaks the [standard contract](docs/standard-io-contract.md).
- **All solvers use the same matrix.** Using one raw-OSRM matrix per instance isolates *routing
  algorithm quality* from ETA/traffic modeling — a fair, apples-to-apples comparison.
- **Metrics recompute from `(instance, solution)` alone**, so anyone can verify the numbers.

## Running the Routific engine

The open-source competitors in this repo are fully runnable. **Routific's own v3 engine is not
runnable from this repository.** To reproduce the Routific results in an isolated environment,
**[contact Routific](https://routific.com)** — we will help you set it up. The Routific results
themselves are published here so the comparison is complete.

## Anonymization & data provenance

The customer-derived dataset is anonymized: coordinates are **donut-geomasked** (displaced from their
true location) and every street address is removed — see the dataset methodology doc. The Standard
Instance format (see the contract) *by construction* carries no address or customer/job identifiers.

## License

- **Code** — [Apache-2.0](LICENSE).
- **`public-benchmark` dataset** — [CC BY-NC 4.0](datasets/public-benchmark/LICENSE) (attribution, non-commercial).
- **OpenStreetMap** — the travel-time matrices are a Produced Work over OSM data; any use must retain
  *"© OpenStreetMap contributors"* (ODbL).

Full attribution requirements are in [`NOTICE`](NOTICE). Third-party solver licenses will be listed in
`THIRD-PARTY.md` as harnesses are added.
