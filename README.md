# Routing Quality Benchmark

An open, **reproducible** benchmark comparing vehicle-routing (VRP) solvers on real-world,
anonymized delivery problems — measuring not just total travel time, but the qualities that make a
route *good to drive*: compactness, non-overlapping/non-crossing routes, balanced workloads, and
fleet utilization.

> **Status: work in progress.** This repo is being built slice by slice. Today it contains the
> standard data contract (below). Datasets, solver harnesses, the runner, and the analyzer land in
> subsequent slices — see [`docs/worklog.md`](docs/worklog.md).

## What's here

| Path | What it is |
|---|---|
| [`docs/standard-io-contract.md`](docs/standard-io-contract.md) | **The foundation** — the Standard Instance & Standard Solution formats every dataset/solver/metric conforms to. |
| [`schema/`](schema/) | JSON Schemas + worked examples for the contract. |
| `datasets/` | Published benchmark datasets as plain files (coming in Slice 2). |
| `solvers/` | Dockerized open-source solver harnesses (coming in Slice 3). |
| `tools/` | Internal tooling used to build the published artifacts. |

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
