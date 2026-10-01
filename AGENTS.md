# AGENTS.md — fedproc-constrained

Third portfolio project for Raihan Sikder. Target roles: Noeon Research (Senior ML Engineer LLMOps, Senior Backend Automated Reasoning), VISASQ, Treasure AI, LegalOn — all Tokyo/Japan.

Siblings: `../flipgate/` (found clause fabrication: AWQ +14.8pts hallucinations) and `../graphproof-qa/` (xgrammar integration already debugged there, incl. KV-cached constrained loop).
Prep context: `../../noeon-prep/`.

---

## Active project: FedProc-Constrained

Compile the 1,032-clause FAR/DFARS registry into a decoding grammar so a small LLM cannot output a nonexistent clause number — then measure the real finding: how often the blocked fake turns into a real-but-wrong clause (substitution rate), and what the grammar costs in speed.

**Publishes:** substitution rate (blocked-fake → real-but-wrong) + latency overhead of constrained vs unconstrained decoding on clause-citation prompts.

### Honesty rules (load-bearing)

- "0% hallucination" is **true by construction** once the grammar allows only registry IDs. NEVER present it as the win. The substitution rate is the result.
- The cheap post-hoc filter (regex-extract + registry-check + retry/repair) is a required baseline. If the grammar only ties it, the finding is "guarantees, not accuracy" — still defensible, say so.
- Only the real-FAR slice for eval; Claude-written synthetic records stay out (same rule as FlipGate).

### Key design decisions

- **Two grammars:** (a) full-registry enum grammar (all ~1.1k IDs valid); (b) per-request input-span grammar (only IDs appearing in the input text valid — tighter, tests whether narrowing helps or hurts).
- **Registry reused, not rebuilt:** `../flipgate/data/eval/far_registry.json` (1,128 canonical numbers from ECFR Title 48). Copy it in with checksum; do not re-derive.
- **Substitution measurement:** prompts engineered to elicit fabrication (obscure topics, near-miss clause numbers); for each blocked fake, record what the model emits instead — correct clause, wrong-but-real clause (substitution), or abstention/refusal.
- **Speed measurement:** tokens/s constrained vs unconstrained on the same prompts; trie/grammar compile time reported (xgrammar lessons from graphproof-qa apply directly).
- **Optional QLoRA:** Qwen2.5-1.5B on the 1,129 FedProc train records (<1h) to test whether fine-tuning changes the substitution pattern. Base-model-only first; LoRA only if base results warrant it.

### Hardware

One RTX 3060 12GB. Qwen2.5-1.5B-Instruct (already downloaded in graphproof-qa — copy, don't re-download). No rented GPU needed. Optional ~$5 A40 check on Qwen2.5-7B-Instruct-AWQ.

### Stack

Python, PyTorch, HF Transformers + PEFT (QLoRA), xgrammar (JSON-schema enum + per-request grammars), Lark (response parser for evaluation, not generation), pytest.

### Milestones (~10 days)

1. **Registry + grammars** (3d) — registry copied with checksum; enum grammar + input-span grammar builders; pytest: every registry ID accepted, made-up IDs rejected; compile times reported.
2. **Substitution measurement** (4d) — fabrication-eliciting prompt set; constrained vs unconstrained vs post-hoc-filter comparison; substitution rate table with CIs; latency table.
3. **Release** (3d) — repo, HF dataset (prompts + per-item outputs), dev.to write-up stating plainly what is by construction.

### Risks to keep honest

- Grammar guarantees 0% invented clauses by construction — never the headline.
- Constrained decoding may tie the cheap filter — report "guarantees, not accuracy".
- Substitution needs enough fabrication-eliciting prompts; pilot the prompt set first and report the elicitation rate.

---

## Conventions

- Python 3.10+, pytest for grammar accept/reject, registry integrity, scorer.
- Own venv (`.venv/`); torch cu124 matching graphproof-qa (known-good with xgrammar).
- Per-item JSONL results, append-only; every claim cites run ID.
- No LLM-as-judge. Registry membership checks only.
