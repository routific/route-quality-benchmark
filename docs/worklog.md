# Worklog

A running, dated log of what was built and **why** — the raw material for the eventual methodology &
research write-up (Slices 6–7). Newest first.

---

## 2026-07-01 — Slice 5: comparison analyzer (no composite score)

**Goal (per Rodrigo).** Not a single score — a **comparison** across solvers of travel time + the
route-quality metrics (crossings between/within routes, workload imbalance, route-duration variance,
idle time) + vehicle count.

**What was built.**
- [`analysis/compute_metrics.py`](../analysis/compute_metrics.py) — recomputes every metric from an
  `(instance, solution)` pair alone, **ported to match `engine-bench analyze compute`**
  (engine-lib `fitness.rs` + routing-engine-api `solution_timeline.rs`/`utils.rs`).
- [`analysis/analyze.py`](../analysis/analyze.py) — aggregates `results/<solver>/<instance>.json` into a
  per-metric mean table + a win-rate table; writes `results/_analysis/*.csv`.
  `--include-provisional` also shows routific-* (flagged not-comparable).
- [`analysis/README.md`](../analysis/README.md) — formal definitions + grounding in Rossit et al. (2019)
  visual-attractiveness (compactness / non-crossing / low-complexity).

**Metric correction (Rodrigo caught the first version was wrong).** My initial guesses didn't match the
engine. Fixed to the real formulas: **workload_imbalance = Σ|route visit-count − avg visit-count|**
(`fitness.deviation_from_balance`, balances stop *count*, not time); **route_duration_variance =
max − min of (travel+service+idle)** per route (`fitness.max_duration_variance`, a *range*, not a
statistical variance); **inter-route crossings only between ADJACENT routes** (nearest-neighbor
`VehicleAdjacency` + full-connect), visit-legs only; intra-route excludes the first↔last wrap. Fidelity
gap: `reroute_incompatible_edges` not ported.

**Runtime removed (was misleading).** The runtime column measured different things per solver (VROOM's
own solve time at fixed `explore` effort ≈ ms; PyVRP/OR-Tools a **flat, arbitrary 4 s budget I set**;
jsprit client wall-clock incl. HTTP, capped at 2000 iterations). Not a fair speed comparison, so it's
dropped from the analyzer. Returns with (a) one clock (server-side pure solve time) + (b) a per-problem
budget from a valid Routific run (internal benchmark uses ≈2× EngineV3's per-problem runtime).

**Run (4 competitors × 5 instances).** VROOM lowest travel + zero inter-route crossings; jsprit worst on
crossings. Tables reproduce the target format.

**Open items.** Routific column stays provisional until v3 is re-run on the Standard Instances; add a
fair runtime protocol; scale 5 → full 200 when ready.

---

## 2026-07-01 — Slice 4 (scoped to 5 instances): batch runner + results

**Goal.** Generate real cross-solver results on a small sample (5 instances) to unblock Slice 5
(metrics), rather than running the full 200.

**What was built.**
- [`run_benchmark.py`](../run_benchmark.py) — brings each solver's Docker service up, solves a set of
  instances via the solver's `run.py` (→ `results/<solver>/<instance>.json`), tears it down. Defaults
  to a 5-instance sample (one per VRP type, all ≤400 stops). jsprit auto-skips >400.
- [`tools/import_routific_results.py`](../tools/import_routific_results.py) — pulls Routific's
  precomputed solutions from the internal benchmark DB (v3 isn't runnable) and converts the stored
  `{start_time, permutation}` arrays to Standard Solutions.

**Ran** the 4 competitors over the 5-instance sample (4 s budget for the anytime solvers) → 20 valid
Standard Solutions in `results/{vroom,pyvrp,ortools,jsprit}/`. All complete, in-range, no duplicates.

**Routific comparability issue (found + decided).** Imported Routific LS (bench 2078) + GA (2079), but
they solved the **priority-aware** internal instance, while the published Standard Instance is
**priority-free** (we dropped `priority`) — e.g. pb-0187 has priorities `{20,7,1,5}`, and Routific left
10 unserved vs competitors' 6 (it optimized priority-weighted, not raw count). Runtimes also differ
(Routific ~44 ms vs the 4 s competitor budget). So **the old Routific results are NOT comparable to the
standard-instance competitor results.** Decision (Rodrigo): **proceed to Slice 5 on the 4 competitors**
(mutually comparable); Routific LS/GA kept but **labeled `meta.provisional=true`**. Proper fix = run v3
on the Standard Instances (priority-free, comparable budget) — a follow-up.

**Note.** `results/` is git-ignored (local run artifacts). Published results (incl. a valid Routific
run) will be committed once regenerated.

---

## 2026-07-01 — Slice 3: Solver harnesses (VROOM, PyVRP, OR-Tools, jsprit)

**Goal.** Package the four open-source competitors so each runs on a fresh machine via Docker and
speaks the Standard I/O contract (Standard Instance → Standard Solution). Extracted from four separate
branches in `routing-engine-api` (`rout-2722` / `rout-2728` / `rout-2723` / `origin/ROUT-2725`).

**What was built.**
- [`solvers/common/standard_io.py`](../solvers/common/standard_io.py) — load instance (`.json`/`.gz`),
  write solution, coverage-check.
- **VROOM** (`solvers/vroom/`) — prebuilt image `vroom-docker:v1.15.0`, HTTP :3030; client-side
  `adapter.py` (custom-matrix). `explore: 2` (matches published results).
- **PyVRP** (`solvers/pyvrp/`) — built image (python:3.12 + `pyvrp`), HTTP :5002; reuses the internal
  `solve.py` Model builder + a Standard-contract server. Needs a C++ toolchain on arm64 (no aarch64
  wheel) — Dockerfile adds `build-essential`.
- **OR-Tools** (`solvers/ortools/`) — built image (+ `ortools`), HTTP :5001; same server pattern.
- **jsprit** (`solvers/jsprit/`) — Java service (gradle shadowJar → JRE), HTTP :8080; client-side
  `adapter.py`. Single capacity dimension (typed collapsed to scalar); ≲400-stop cap; no self-reported
  solve time (client wall-clock).
- [`THIRD-PARTY.md`](../THIRD-PARTY.md) — upstream licenses (VROOM BSD-2, PyVRP MIT, OR-Tools Apache-2,
  jsprit Apache-2) + jsprit's Javalin/Jackson/SLF4J.

**`minimize_vehicles` (Rodrigo's correctness note, applied to all solvers).** When set, each solver
charges a per-vehicle fixed cost calibrated *below the value of serving a visit*, so it consolidates
routes but never drops a servable stop to save a vehicle (**serve > vehicles > travel time**). VROOM
had this gap (its default minimizes travel time, not vehicle count) — added `costs.fixed`; verified it
cut routes 2→1 with unserved unchanged. PyVRP (`fixed_cost` < prize) and OR-Tools (fixed cost < drop
penalty) already had it; jsprit uses `maxCost×20`.

**Verification.** Every solver ran the 5 constraint types (tsp/vrp/cvrp/vrptw/cvrptw) → all produced
valid Standard Solutions (in-range indices, full coverage, no duplicates). Cross-check on a
minimize-vehicles instance: PyVRP/OR-Tools → 1 route, VROOM/jsprit → 2 routes, all with the same 1
unserved — the real solver-quality spread the benchmark measures.

**Deferred.** A batch runner over the whole dataset + Routific's own results = Slice 4. jsprit's
≲400-stop skip is enforced there.

---

## 2026-07-01 — Slice 2: Publish the `public-benchmark` dataset

**Goal.** Export the 200 `public-benchmark` instances to files that conform to the Slice-1 contract,
segregated by VRP type, with a manifest — the routific dataset (Amazon deferred).

**What was built.**
- [`tools/export_public_benchmark.py`](../tools/export_public_benchmark.py) — reads internal cached
  instances and emits Standard Instances. PII removal is not special-cased: it builds the contract
  shape, so `locations` end up coords-only and the dropped fields never appear. Includes an
  `assert_clean()` guard (fails if any off-contract/PII field or non-N×N matrix survives).
- Ran it → `datasets/public-benchmark/<type>/pb-XXXX.json` (200 files) + `manifest.csv` +
  `_provenance.private.csv` (gitignored map `pb-XXXX → internal id / original_problem_id`).
- [`datasets/public-benchmark/README.md`](../datasets/public-benchmark/README.md) — dataset card.

**Transforms applied (internal → Standard Instance).**
- `locations` → `{lat, lng}` only (address `name` + internal `id` dropped).
- ids anonymized: `veh-N`, `visit-N`, instance `pb-XXXX` (sequential by internal id).
- dropped `speed`, `priority`, `etas_options`, `secondary_objective` (except `minimize_vehicles`).
- classified by VRP type from content: cvrp 84, vrptw 53, vrp 46, cvrptw 14, tsp 3.

**Verification.** Independent scan of all 200 output files: **0 structural errors** (every matrix is
N×N, all indices in range) and **0 unexpected strings** — every string is `pb-XXXX` / `veh-N` /
`visit-N` / a type label, proving no address leaked.

**Storage.** Matrices dominate (largest instance is 3,577 stops): pretty JSON = 1.4 GB, minified =
770 MB, **minified + gzip = 294 MB** (largest single file 24 MB, within GitHub's 100 MB limit).
Decision (Rodrigo): **gzip each file in-repo** — instances stored as minified `.json.gz`
(`json.load(gzip.open(path))`). Re-verified the gz form: 200 readable, 0 errors, 0 leaked strings.

**Gates (all resolved 2026-07-01).**
- ~~Coordinate-masking verification~~ **RESOLVED** — verified manually by Rodrigo.
- ~~Licensing~~ **RESOLVED** — code = **Apache-2.0** (`LICENSE` + `NOTICE`); `public-benchmark` dataset =
  **CC BY-NC 4.0** (`datasets/public-benchmark/LICENSE`); **OSM attribution required** (matrices are a
  Produced Work over OpenStreetMap/ODbL — "© OpenStreetMap contributors"). Third-party solver licenses
  → `THIRD-PARTY.md` (Slice 3).
- ~~OSRM map version~~ **RESOLVED** (2026-07-01) — read from `kstaging` cluster, `osrm` namespace:
  OSRM **v6.0.0** (`project-osrm/osrm-backend`, CH, `--max-table-size 8000`) over Geofabrik
  `<region>-latest` extracts. Dataset spans 6 regions; extract dates: **europe 2026-05-10**, all others
  (na/au-oceania/africa/south-america/asia) **2026-06-25**. Recorded in the dataset card. Caveat: the
  06-25 regions were rebuilt around the matrix-construction window, so alignment is approximate to that
  date; Europe's extract predates construction (exact match).
- Dataset license.

**Next.** Slice 3 (solver harnesses) or the coord-masking gate, per Rodrigo.

---

## 2026-07-01 — Slice 1: Standard I/O contract

**Goal.** Define the Standard Instance & Standard Solution formats before touching any data, so the
whole repo has one contract and PII removal is a designed-in property of the format.

**What was decided/built.**
- Wrote [`docs/standard-io-contract.md`](standard-io-contract.md) + JSON Schemas
  ([`schema/instance.schema.json`](../schema/instance.schema.json),
  [`schema/solution.schema.json`](../schema/solution.schema.json)) + examples.
- **Standard Instance** = index-spaced `locations` (coords only) + `vehicles` + `visits` +
  `distances` (raw-OSRM, seconds) + `etas_options` + `secondary_objective`, tagged with `name` and
  VRP `type`.
- **Standard Solution** = per-route ordered **permutation of visit indices** + `unserved` +
  `runtime_ms`. Metrics recompute from `(instance, solution)` alone.
- **Fields excluded by design:** `locations[].name` (street address — PII), `locations[].id`
  (redundant with index), `user_id`/`job_id`, `original_problem_id`.
- **Format simplified per review (Rodrigo):** dropped `visits[].priority`, `vehicles[].speed`, all of
  `etas_options` (⇒ published as the **hard-constrained** version, matching the benchmark's own
  `remove_soft_constraints`), and `secondary_objective` except `minimize_vehicles` (promoted to a
  top-level flag). Caveat: `speed` was non-unit in **31/200** instances (24 mixed-speed fleets) —
  dropping normalizes those to uniform speed (reversible if the heterogeneous-fleet effect matters).

**Grounding facts (from the internal benchmark tool).**
- Source instances live in the `BENCHMARK_DATABASE_URL` Postgres (groups/`group_problems`/`problems`)
  with instance JSON cached in `$BENCHMARK_CACHE` (`instance-<id>-0.json`).
- The publishable Routific dataset is DB group **`public-benchmark`** = **200 curated instances**
  (drawn from the 7,570-instance `public-osrm-masked` pool). All 200 files are present in the local
  cache.
- **PII in the raw set:** **181 / 200** instances carry real street addresses in `locations[].name`
  (103,678 address strings total). The contract removes this field entirely.
- **Format variance encoded in the schema:** `capacity`/`demand` are scalar **or** typed-object
  `{key: number}` **or** null; `time_windows` values are mostly relative seconds but 131 are absolute
  unix-epoch.
- **VRP-type distribution of the 200** (classifier `tools/vrp_classify.py`, derived purely from
  instance content): cvrp 84, vrptw 53, vrp 46, cvrptw 14, tsp 3.

**Open items surfaced.**
- **Coordinate-masking verification:** the `public-benchmark` instances have `original_problem_id`
  set (created by the masking pipeline) but coordinate displacement could not be verified locally (no
  S3/AWS CLI). **Gate: confirm coords are genuinely geomasked before any public push.**
- Repo home / visibility (currently local-only at `~/projects/routific-benchmark`).
- Time normalization (relative vs absolute epoch) — decide at export (Slice 2).
- Code vs data licensing (see README).

**Next.** Slice 2 — export the 200 `public-benchmark` instances to files conforming to this contract,
segregated by VRP type, with a manifest. The exporter's PII removal is now just "conform to the
contract".
