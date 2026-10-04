#!/usr/bin/env python3
"""Summarise data/runs_v2.json: outcome counts per prompt kind x condition, Wilson 95% intervals
for the headline rates, and the overall good rate. Writes results/v2_summary.json and prints markdown.

Usage: python scripts/summarize_v2.py [--runs data/runs_v2.json]
"""
import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

CONDITIONS = ["unconstrained", "unconstrained_abstain", "enum", "enum_abstain", "posthoc"]
KINDS = ["fake_topic", "real_clause", "absent_number", "obscure_real"]
GOOD = {"correct", "abstain_correct"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "ci95": [round(lo, 3), round(hi, 3)]}


def title_of(resp: str):
    m = re.search(r'"title"\s*:\s*"([^"]*)"', resp)
    return m.group(1).strip() if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="data/runs_v2.json")
    ap.add_argument("--out", default="results/v2_summary.json")
    args = ap.parse_args()
    d = json.load(open(args.runs))
    rows = d["rows"]
    out = {"model": d["model"], "n_prompts": len(rows), "counts": {}, "headline": {}}
    for c in CONDITIONS:
        out["counts"][c] = {k: dict(Counter(r[c]["outcome"] for r in rows if r["kind"] == k)) for k in KINDS}
        no_gold = [r for r in rows if r["kind"] != "real_clause"]  # prompts where nothing can be cited as "the" answer
        judged = [r for r in rows if r["kind"] in ("fake_topic", "real_clause", "absent_number")]
        out["headline"][c] = {
            "fabricated_on_non_real_prompts": rate(sum(r[c]["outcome"] == "fabrication" for r in no_gold), len(no_gold)),
            "good_answer_overall": rate(sum(r[c]["outcome"] in GOOD for r in judged), len(judged)),
            "abstain_correct_fake_topic": rate(sum(r[c]["outcome"] == "abstain_correct" for r in rows if r["kind"] == "fake_topic"), 30),
            "abstain_correct_absent_number": rate(sum(r[c]["outcome"] == "abstain_correct" for r in rows if r["kind"] == "absent_number"), 15),
            "abstain_wrong_real_clause": rate(sum(r[c]["outcome"] == "abstain_wrong" for r in rows if r["kind"] == "real_clause"), 15),
            "correct_real_clause": rate(sum(r[c]["outcome"] == "correct" for r in rows if r["kind"] == "real_clause"), 15),
            "hit_token_cap": sum(r[c]["hit_cap"] for r in rows),
        }
    # The registry holds IDs only, so titles cannot be graded. Diversity is a proxy: 15 different clauses
    # should not share a handful of titles.
    out["title_diversity_real_clause"] = {}
    for c in CONDITIONS:
        ts = [title_of(r[c]["response"]) for r in rows if r["kind"] == "real_clause" and r[c]["outcome"] == "correct"]
        cnt = Counter(ts)
        out["title_diversity_real_clause"][c] = {"n_correct_ids": len(ts), "distinct_titles": len(cnt),
                                                 "most_common_title_count": cnt.most_common(1)[0][1] if cnt else 0}
    Path(args.out).parent.mkdir(exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)

    def fmt(x):
        return f"{x['k']}/{x['n']} ({x['rate']:.0%}, [{x['ci95'][0]:.0%}, {x['ci95'][1]:.0%}])"
    print(f"{'condition':22} {'fabricated (non-real, n=60)':34} {'good answer (n=60)':28} {'abstain ok: fake':26} {'abstain ok: absent':26} {'abstain WRONG: real':26}")
    for c in CONDITIONS:
        h = out["headline"][c]
        print(f"{c:22} {fmt(h['fabricated_on_non_real_prompts']):34} {fmt(h['good_answer_overall']):28} "
              f"{fmt(h['abstain_correct_fake_topic']):26} {fmt(h['abstain_correct_absent_number']):26} {fmt(h['abstain_wrong_real_clause']):26}")
    print("\nTitle diversity on the real-clause prompts (correct IDs only; the 15 prompts name 15 different clauses):")
    for c in CONDITIONS:
        t = out["title_diversity_real_clause"][c]
        if t["n_correct_ids"]:
            print(f"  {c:22} {t['n_correct_ids']} correct IDs -> {t['distinct_titles']} distinct titles (most common used {t['most_common_title_count']}x)")
    print("saved ->", args.out)


if __name__ == "__main__":
    main()
