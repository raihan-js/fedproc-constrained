#!/usr/bin/env python3
"""v2 experiment: 75 prompts x 5 conditions, with and without an abstain option.

Conditions:
  unconstrained            free generation (v1 baseline)
  unconstrained_abstain    free generation, prompt also allows {"clause": "NONE"}
  enum                     xgrammar, registry IDs only (v1 enum condition)
  enum_abstain             xgrammar, registry IDs or "NONE", prompt allows NONE
  posthoc                  free generation + registry check + one retry (v1 condition)

Records the cited ID, the v2 outcome class, tokens/s and whether the generation hit the cap.
Usage: PYTHONPATH=src python scripts/run_v2.py [--model data/models/Qwen--Qwen2.5-1.5B-Instruct]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_constrained import build_matcher, generate_constrained, generate_free  # noqa: E402

from fedconstrained.grammar.builder import (  # noqa: E402
    canonicalize, extract_json_clause, full_registry_grammar, is_registry_id, load_registry)
from fedconstrained.outcomes import KINDS, classify_v2  # noqa: E402

ABSTAIN_SUFFIX = ' If no FAR or DFARS clause applies, or the clause does not exist, reply {"clause": "NONE", "title": ""}.'
CAP = 256
CONDITIONS = ["unconstrained", "unconstrained_abstain", "enum", "enum_abstain", "posthoc"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="data/prompts_v2.json")
    ap.add_argument("--model", default="data/models/Qwen--Qwen2.5-1.5B-Instruct")
    ap.add_argument("--out", default="data/runs_v2.json")
    ap.add_argument("--limit", type=int, default=None, help="only the first N prompts (smoke test)")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    registry = set(load_registry("data/registry/far_registry.json"))
    prompts = json.load(open(args.prompts))[: args.limit]
    print(f"registry {len(registry)} IDs, {len(prompts)} prompts, model {args.model}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16 if args.device == "cuda" else torch.float32,
                                                 device_map=args.device, pad_token_id=tok.pad_token_id)
    model.eval()
    enum_c, _ = build_matcher(tok, full_registry_grammar(sorted(registry))[0])
    enum_abs_c, _ = build_matcher(tok, full_registry_grammar(sorted(registry), allow_abstain=True)[0])

    def cell(item, resp, ntok, dt, extra=None):
        cited = extract_json_clause(resp)
        d = {"cited": cited, "outcome": classify_v2(item["kind"], item.get("gold"), cited, registry),
             "tokens_per_s": round(ntok / dt, 1) if dt else None, "hit_cap": ntok >= CAP, "response": resp[:300]}
        d.update(extra or {})
        return d

    rows = []
    for i, item in enumerate(prompts):
        plain = [{"role": "user", "content": item["prompt"]}]
        abst = [{"role": "user", "content": item["prompt"] + ABSTAIN_SUFFIX}]
        row = {"kind": item["kind"], "gold": item.get("gold"), "prompt": item["prompt"]}
        row["unconstrained"] = cell(item, *generate_free(model, tok, plain, CAP))
        row["unconstrained_abstain"] = cell(item, *generate_free(model, tok, abst, CAP))
        row["enum"] = cell(item, *generate_constrained(model, tok, enum_c, plain, CAP))
        row["enum_abstain"] = cell(item, *generate_constrained(model, tok, enum_abs_c, abst, CAP))
        resp, ntok, dt = generate_free(model, tok, plain, CAP)
        first, cited = resp, extract_json_clause(resp)
        if cited is None or not is_registry_id(canonicalize(cited), registry):
            retry = [{"role": "user", "content": item["prompt"] + " Cite ONLY a real FAR or DFARS clause number."}]
            resp, n2, dt2 = generate_free(model, tok, retry, CAP)
            ntok, dt = ntok + n2, dt + dt2
        row["posthoc"] = cell(item, resp, ntok, dt, {"first_response": first[:200]})
        rows.append(row)
        print(f"[{i+1}/{len(prompts)}] {item['kind']:13} " + " ".join(f"{c}={row[c]['outcome']}" for c in CONDITIONS), flush=True)

    json.dump({"model": args.model, "registry_size": len(registry), "cap": CAP, "rows": rows}, open(args.out, "w"), indent=2)

    print("\nOutcomes by kind x condition:")
    for kind in KINDS:
        sub = [r for r in rows if r["kind"] == kind]
        if not sub:
            continue
        print(f"\n{kind} (n={len(sub)})")
        for c in CONDITIONS:
            cnt = Counter(r[c]["outcome"] for r in sub)
            print(f"  {c:22} {dict(cnt)}")
    capped = defaultdict(int)
    for r in rows:
        for c in CONDITIONS:
            capped[c] += r[c]["hit_cap"]
    print("\ngenerations that hit the", CAP, "token cap:", dict(capped))
    print("saved ->", args.out)


if __name__ == "__main__":
    main()
