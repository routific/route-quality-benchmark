# Worklog

A running, dated log of what was built and **why** — the raw material for the eventual methodology &
research write-up (Slices 6–7). Newest first.

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
