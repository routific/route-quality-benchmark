#!/usr/bin/env python3
"""Combine Routific LS + GA outputs into a single per-problem best-of "Routific".

The public benchmark reports one Routific column, not LS and GA separately. For each
instance solved by both, pick the better solution by the objective hierarchy
**serve > vehicles > travel time** (fewest unserved, then fewest vehicles, then lowest
travel time) and write it to results/routific/<instance>.json (solver="routific",
meta.best_of = "ls" | "ga").

  python3 tools/routific_best_of.py
"""
from __future__ import annotations
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analysis"))
from compute_metrics import compute  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(REPO, "datasets", "public-benchmark")
RESULTS = os.path.join(REPO, "results")


def load_instance(name: str) -> dict:
    with gzip.open(glob.glob(os.path.join(DATASET, "*", f"{name}.json.gz"))[0], "rb") as f:
        return json.load(f)


def score(instance: dict, solution: dict):
    m = compute(instance, solution)
    return (m["num_unserved"], m["num_vehicles"], m["travel_time"])  # lower is better, lexicographically


def main() -> int:
    ls_dir, ga_dir = os.path.join(RESULTS, "routific-ls"), os.path.join(RESULTS, "routific-ga")
    ls = {os.path.basename(f)[:-5] for f in glob.glob(f"{ls_dir}/*.json")}
    ga = {os.path.basename(f)[:-5] for f in glob.glob(f"{ga_dir}/*.json")}
    both = sorted(ls & ga)
    if not both:
        sys.exit("need results in BOTH results/routific-ls/ and results/routific-ga/ first")

    out = os.path.join(RESULTS, "routific")
    os.makedirs(out, exist_ok=True)
    wins = {"ls": 0, "ga": 0}
    for name in both:
        inst = load_instance(name)
        s_ls = json.load(open(f"{ls_dir}/{name}.json"))
        s_ga = json.load(open(f"{ga_dir}/{name}.json"))
        pick, tag = (s_ls, "ls") if score(inst, s_ls) <= score(inst, s_ga) else (s_ga, "ga")
        wins[tag] += 1
        best = dict(pick)
        best["solver"] = "routific"
        best.setdefault("meta", {})
        best["meta"]["best_of"] = tag
        json.dump(best, open(f"{out}/{name}.json", "w"), separators=(",", ":"))

    print(f"combined {len(both)} instances -> results/routific/  (LS won {wins['ls']}, GA won {wins['ga']})")
    only = (ls - ga, ga - ls)
    if only[0] or only[1]:
        print(f"  note: {len(only[0])} only in LS, {len(only[1])} only in GA (skipped — need both)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
