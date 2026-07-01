#!/usr/bin/env python3
"""Export the `public-benchmark` group to Standard Instance files (Slice 2).

Reads Routific's internal cached instances and emits files that conform to the
Standard Instance contract (see docs/standard-io-contract.md):
  - locations reduced to coordinates only  (street address / internal id removed)
  - ids anonymized to sequential labels
  - Routific-specific/soft fields dropped   (speed, priority, etas_options,
    secondary_objective except minimize_vehicles)
  - each instance classified by VRP type and written under datasets/<type>/

Because the exporter's only job is "make the raw instance match the contract",
PII removal is not special-cased here — it falls out of building the contract shape.

Inputs (internal, not published):
  --ids-file   newline-separated internal problem ids of the group   (default: tools/_private/public-benchmark.ids)
  --meta-file  TSV `id\tnum_visits\tnum_vehicles\toriginal_problem_id` for provenance (optional)
  --cache      dir of internal `instance-<id>-0.json` files          (default: $BENCHMARK_CACHE or ~/benchmark_cache)

Outputs:
  <out>/<type>/pb-XXXX.json          the published Standard Instances
  <out>/manifest.csv                 public manifest (no internal linkage)
  <out>/_provenance.private.csv      private map pb-XXXX -> internal ids (gitignored)
"""
from __future__ import annotations
import argparse, csv, gzip, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vrp_classify import classify, _has_capacity, _has_time_windows, _has_pdp  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_standard(raw: dict, name: str) -> dict:
    """Transform an internal cached instance into a Standard Instance."""
    locations = []
    for loc in raw.get("locations", []):
        c = loc.get("coords") or {}
        # coordinates ONLY — address (`name`) and internal `id` are dropped by omission
        locations.append({"lat": c.get("lat"), "lng": c.get("lng")})

    vehicles = []
    for i, v in enumerate(raw.get("vehicles", [])):
        vehicles.append({
            "id": f"veh-{i}",                       # anonymized label
            "start_location": v.get("start_location"),
            "end_location": v.get("end_location"),
            "shift_start_time": v.get("shift_start_time"),
            "shift_end_time": v.get("shift_end_time"),
            "capacity": v.get("capacity"),          # scalar | typed dict | null (kept as-is)
        })                                          # dropped: speed, priority, breaks, types, ...

    visits = []
    for i, x in enumerate(raw.get("visits", [])):
        tw = [{"start": w.get("start"), "end": w.get("end")} for w in (x.get("time_windows") or [])]
        prec = x.get("precedence")
        prec = None if prec in (None, "None") else prec
        visits.append({
            "id": f"visit-{i}",                     # anonymized label
            "location": x.get("location"),
            "duration": x.get("duration"),
            "time_windows": tw,
            "demand": x.get("demand"),              # scalar | typed dict | null (kept as-is)
            "precedence": prec,
        })                                          # dropped: priority, inventory, types

    so = raw.get("secondary_objective") or {}
    inst = {
        "name": name,
        "type": None,
        "locations": locations,
        "vehicles": vehicles,
        "visits": visits,
        "distances": raw.get("distances"),
        "minimize_vehicles": bool(so.get("minimize_vehicles", False)),
    }
    inst["type"] = classify(inst)
    return inst


def assert_clean(inst: dict, src_id: str) -> None:
    """Fail loudly if any PII / off-contract field survived."""
    for loc in inst["locations"]:
        assert set(loc.keys()) == {"lat", "lng"}, f"{src_id}: location has extra keys {set(loc)}"
        assert loc["lat"] is not None and loc["lng"] is not None, f"{src_id}: location missing coords"
    N = len(inst["locations"])
    d = inst["distances"]
    assert isinstance(d, list) and len(d) == N and all(isinstance(r, list) and len(r) == N for r in d), \
        f"{src_id}: distances is not an {N}x{N} matrix"
    for v in inst["vehicles"]:
        assert "speed" not in v and "priority" not in v, f"{src_id}: vehicle off-contract"
    for x in inst["visits"]:
        assert "priority" not in x, f"{src_id}: visit off-contract"
    assert "etas_options" not in inst and "secondary_objective" not in inst, f"{src_id}: off-contract top-level"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids-file", default=os.path.join(REPO, "tools", "_private", "public-benchmark.ids"))
    ap.add_argument("--meta-file", default=os.path.join(REPO, "tools", "_private", "public-benchmark.meta.tsv"))
    ap.add_argument("--cache", default=os.environ.get("BENCHMARK_CACHE", os.path.expanduser("~/benchmark_cache")))
    ap.add_argument("--out", default=os.path.join(REPO, "datasets", "public-benchmark"))
    args = ap.parse_args()

    ids = [l.strip() for l in open(args.ids_file) if l.strip()]
    ids.sort(key=lambda s: int(s))                  # stable order → stable pb-XXXX numbering

    provenance = {}                                 # src_id -> original_problem_id
    if os.path.exists(args.meta_file):
        for row in open(args.meta_file):
            parts = row.rstrip("\n").split("\t")
            if len(parts) >= 4:
                provenance[parts[0]] = parts[3]

    manifest_rows, provenance_rows = [], []
    counts = {}
    for seq, src_id in enumerate(ids, start=1):
        name = f"pb-{seq:04d}"
        raw = json.load(open(os.path.join(args.cache, f"instance-{src_id}-0.json")))
        inst = build_standard(raw, name)
        assert_clean(inst, src_id)

        type_dir = os.path.join(args.out, inst["type"])
        os.makedirs(type_dir, exist_ok=True)
        # Stored gzipped + minified: matrices are huge (up to ~3.5k x 3.5k). The *format* is the
        # Standard Instance JSON; `.gz` is only on-disk encoding. Read with: json.load(gzip.open(path)).
        payload = json.dumps(inst, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with gzip.open(os.path.join(type_dir, f"{name}.json.gz"), "wb", compresslevel=6) as f:
            f.write(payload)

        counts[inst["type"]] = counts.get(inst["type"], 0) + 1
        manifest_rows.append({
            "name": name, "type": inst["type"],
            "num_visits": len(inst["visits"]), "num_vehicles": len(inst["vehicles"]),
            "num_locations": len(inst["locations"]),
            "has_capacity": _has_capacity(inst), "has_time_windows": _has_time_windows(inst),
            "has_pdp": _has_pdp(inst), "minimize_vehicles": inst["minimize_vehicles"],
        })
        provenance_rows.append({"name": name, "source_instance_id": src_id,
                                "original_problem_id": provenance.get(src_id, "")})

    with open(os.path.join(args.out, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        w.writeheader(); w.writerows(manifest_rows)
    with open(os.path.join(args.out, "_provenance.private.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "source_instance_id", "original_problem_id"])
        w.writeheader(); w.writerows(provenance_rows)

    print(f"exported {len(ids)} instances -> {args.out}")
    for t in sorted(counts): print(f"  {t}: {counts[t]}")
    print("manifest.csv + _provenance.private.csv written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
