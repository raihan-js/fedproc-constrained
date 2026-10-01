#!/usr/bin/env python3
"""Unconstrained pilot: measure fabrication elicitation rate.

Runs each prompt on the base model with no constraint, extracts the cited
clause ID, and checks registry membership. Establishes whether the prompt
set elicits enough fabrication to measure substitution against.
Usage: PYTHONPATH=src python scripts/run_pilot.py
"""
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from fedconstrained.grammar.builder import (
    extract_json_clause,
    is_registry_id,
    load_registry,
)


def main() -> None:
    print("Loading registry...", flush=True)
    registry = set(load_registry("data/registry/far_registry.json"))
    prompts = json.load(open("data/prompts_pilot.json"))
    print(f"Registry: {len(registry)}, prompts: {len(prompts)}", flush=True)

    print("Loading model...", flush=True)
    model_path = "data/models/Qwen--Qwen2.5-1.5B-Instruct"
    tok = AutoTokenizer.from_pretrained(model_path, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="cuda",
        pad_token_id=tok.pad_token_id)
    model.eval()
    print("Model loaded", flush=True)

    results = []
    fabricated = 0
    start = time.time()
    for i, item in enumerate(prompts):
        messages = [{"role": "user", "content": item["prompt"]}]
        formatted = tok.apply_chat_template(messages, tokenize=False,
                                            add_generation_prompt=True)
        inputs = tok(formatted, return_tensors="pt").to(model.device)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        dt = time.time() - t0
        n_tokens = len(out[0]) - inputs.input_ids.shape[1]
        resp = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        cited = extract_json_clause(resp)
        in_reg = cited is not None and is_registry_id(cited, registry)
        if cited is not None and not in_reg:
            fabricated += 1
        results.append({"kind": item["kind"], "prompt": item["prompt"][:120],
                        "response": resp[:400], "cited": cited,
                        "in_registry": in_reg, "tokens": n_tokens,
                        "seconds": round(dt, 2),
                        "tokens_per_s": round(n_tokens / dt, 1)})
        print(f"  [{i+1}/{len(prompts)}] {item['kind']}: cited={cited} in_reg={in_reg}",
              flush=True)

    elapsed = time.time() - start
    print(f"\nFabrication rate: {fabricated}/{len(prompts)} = "
          f"{100*fabricated/len(prompts):.0f}% in {elapsed:.0f}s", flush=True)
    with open("data/runs_pilot.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved -> data/runs_pilot.json", flush=True)


if __name__ == "__main__":
    main()
