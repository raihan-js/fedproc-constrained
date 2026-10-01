#!/usr/bin/env python3
"""Constrained evaluation: enum-grammar + input-span-grammar + post-hoc filter.

Compares four conditions on the same prompts:
  1. unconstrained  (baseline; from pilot data if present)
  2. enum-constrained (xgrammar, full 1056-ID registry)
  3. span-constrained (xgrammar, only IDs mentioned in the input)
  4. posthoc-filter  (unconstrained + regex-extract + registry check + 1 retry)

For each response records: cited ID, in-registry verdict, outcome class
(correct / substitution / fabrication / abstain / malformed), tokens/s.
Usage: PYTHONPATH=src python scripts/run_constrained.py [--prompts data/prompts_pilot.json]
"""
import argparse
import json
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from fedconstrained.grammar.builder import (
    extract_json_clause,
    full_registry_grammar,
    input_span_grammar,
    is_registry_id,
    load_registry,
)

GRAMMAR_VOCAB = 151680  # xgrammar bitmask width for Qwen


def build_matcher(tokenizer, ebnf: str):
    import xgrammar as xgr
    t0 = time.time()
    info = xgr.TokenizerInfo.from_huggingface(tokenizer)
    compiled = xgr.GrammarCompiler(info).compile_grammar(ebnf)
    return compiled, time.time() - t0


def generate_constrained(model, tokenizer, compiled, messages, max_tokens=256):
    """Greedy + xgrammar mask, KV-cached. Returns (text, n_tokens, seconds)."""
    import xgrammar as xgr

    matcher = xgr.GrammarMatcher(compiled)
    bitmask = xgr.allocate_token_bitmask(1, GRAMMAR_VOCAB)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True)
    prompt_ids = tokenizer(prompt, return_tensors="pt").input_ids[0].tolist()
    generated = list(prompt_ids)
    device = next(model.parameters()).device
    t0 = time.time()
    with torch.no_grad():
        out = model(input_ids=torch.tensor([generated], device=device), use_cache=True)
    past = out.past_key_values
    for _ in range(max_tokens):
        with torch.no_grad():
            out = model(input_ids=torch.tensor([[generated[-1]]], device=device),
                        past_key_values=past, use_cache=True)
        logits = out.logits[0, -1]
        past = out.past_key_values
        matcher.fill_next_token_bitmask(bitmask)
        masked = logits.detach().to("cpu")[:GRAMMAR_VOCAB]
        xgr.apply_token_bitmask_inplace(masked.unsqueeze(0), bitmask)
        nxt = int(torch.argmax(masked))
        if nxt == tokenizer.eos_token_id:
            break
        if not matcher.accept_token(nxt):
            break
        generated.append(nxt)
        if matcher.is_terminated():
            break
    dt = time.time() - t0
    n_new = len(generated) - len(prompt_ids)
    full = tokenizer.decode(generated, skip_special_tokens=True)
    prompt_text = tokenizer.decode(prompt_ids, skip_special_tokens=True)
    text = full[len(prompt_text):] if full.startswith(prompt_text) else full
    return text, n_new, dt


def generate_free(model, tokenizer, messages, max_tokens=256):
    prompt = tokenizer.apply_chat_template(messages, tokenize=False,
                                           add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
    dt = time.time() - t0
    n_new = out.shape[1] - inputs.input_ids.shape[1]
    resp = tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return resp, n_new, dt


def classify(item: dict, cited: str | None, registry: set) -> str:
    """Outcome class for one response."""
    if cited is None:
        return "malformed"
    if not is_registry_id(cited, registry):
        return "fabrication"
    kind, gold = item["kind"], item.get("gold")
    if kind == "fake_topic":
        # No correct clause exists; any citation is a substitution.
        # (Abstention is impossible under the JSON grammar — documented.)
        return "substitution"
    if kind == "near_miss" and gold:
        return "correct" if cited == gold or cited == gold.split()[-1] else "substitution"
    return "registry_valid"  # obscure_real: valid ID, correctness unjudged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="data/prompts_pilot.json")
    ap.add_argument("--model", default="data/models/Qwen--Qwen2.5-1.5B-Instruct")
    ap.add_argument("--out", default="data/runs_constrained.json")
    args = ap.parse_args()

    registry = set(load_registry("data/registry/far_registry.json"))
    prompts = json.load(open(args.prompts))
    print(f"Registry: {len(registry)}, prompts: {len(prompts)}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda",
        pad_token_id=tok.pad_token_id)
    model.eval()

    enum_ebnf, _ = full_registry_grammar(sorted(registry))
    enum_compiled, enum_s = build_matcher(tok, enum_ebnf)
    print(f"Enum grammar compiled in {enum_s:.1f}s", flush=True)

    results = []
    for i, item in enumerate(prompts):
        messages = [{"role": "user", "content": item["prompt"]}]
        row = {"kind": item["kind"], "gold": item.get("gold")}

        # 1. unconstrained
        resp, ntok, dt = generate_free(model, tok, messages)
        cited = extract_json_clause(resp)
        row["unconstrained"] = {"cited": cited, "outcome": classify(item, cited, registry),
                                "tokens_per_s": round(ntok / dt, 1),
                                "response": resp[:300]}

        # 2. enum-constrained
        resp, ntok, dt = generate_constrained(model, tok, enum_compiled, messages)
        cited = extract_json_clause(resp)
        row["enum"] = {"cited": cited, "outcome": classify(item, cited, registry),
                       "tokens_per_s": round(ntok / dt, 1),
                       "response": resp[:300]}

        # 3. span-constrained (grammar built from THIS prompt)
        span_ebnf, _ = input_span_grammar(registry, item["prompt"])
        span_compiled, _ = build_matcher(tok, span_ebnf)
        resp, ntok, dt = generate_constrained(model, tok, span_compiled, messages)
        cited = extract_json_clause(resp)
        outcome = classify(item, cited, registry)
        row["span"] = {"cited": cited, "outcome": outcome,
                       "tokens_per_s": round(ntok / dt, 1),
                       "response": resp[:300]}

        # 4. post-hoc filter: free generation + check + one retry
        resp, ntok, dt = generate_free(model, tok, messages)
        cited = extract_json_clause(resp)
        total_tok, total_dt = ntok, dt
        first_resp = resp
        if cited is None or not is_registry_id(cited, registry):
            retry = [{"role": "user", "content": item["prompt"] + " Cite ONLY a real FAR or DFARS clause number."}]
            resp, ntok2, dt2 = generate_free(model, tok, retry)
            total_tok += ntok2
            total_dt += dt2
            cited = extract_json_clause(resp)
        row["posthoc"] = {"cited": cited, "outcome": classify(item, cited, registry),
                          "tokens_per_s": round(total_tok / total_dt, 1),
                          "response": resp[:300], "first_response": first_resp[:200]}

        print(f"  [{i+1}/{len(prompts)}] {item['kind']}: "
              f"free={row['unconstrained']['outcome']} enum={row['enum']['outcome']} "
              f"span={row['span']['outcome']} posthoc={row['posthoc']['outcome']}", flush=True)
        results.append(row)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    # summary
    from collections import Counter
    print("\nOutcome counts per condition:")
    for cond in ["unconstrained", "enum", "span", "posthoc"]:
        c = Counter(r[cond]["outcome"] for r in results)
        tps = sum(r[cond]["tokens_per_s"] for r in results) / len(results)
        print(f"  {cond:<13} {dict(c)}  avg {tps:.1f} tok/s")
    print(f"Saved -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
