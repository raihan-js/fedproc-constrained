#!/usr/bin/env python3
"""Re-score the v1 runs (data/runs_full.json) with the corrected v2 labels.

v1 called its "near_miss" prompts near misses, but every number they ask about is a real clause,
so the right answer is that number. This relabels them `real_clause` (gold = the number asked
about), canonicalises "FAR 52.222-41"-style answers, and prints outcomes by kind and condition.

Usage: PYTHONPATH=src python scripts/rescore_v1.py
"""
import json
import re
from collections import Counter

from fedconstrained.grammar.builder import load_registry
from fedconstrained.outcomes import classify_v2

registry = set(load_registry("data/registry/far_registry.json"))
prompts = json.load(open("data/prompts_pilot.json"))
runs = json.load(open("data/runs_full.json"))
CONDS = ["unconstrained", "enum", "span", "posthoc"]
table: dict[tuple[str, str], Counter] = {}
for p, r in zip(prompts, runs):
    kind, gold = p["kind"], p.get("gold")
    if kind == "near_miss":
        kind, gold = "real_clause", re.search(r"FAR (\S+) cover", p["prompt"]).group(1)
    for c in CONDS:
        table.setdefault((kind, c), Counter())[classify_v2(kind, gold, r[c]["cited"], registry)] += 1
for kind in ("fake_topic", "real_clause", "obscure_real"):
    print(f"\n{kind}")
    for c in CONDS:
        print(f"  {c:14} {dict(table[(kind, c)])}")
