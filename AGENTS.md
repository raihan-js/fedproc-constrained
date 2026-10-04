# AGENTS.md — fedproc-constrained

Third portfolio project for Raihan Sikder. Target roles: Noeon Research (Senior ML Engineer LLMOps, Senior Backend Automated Reasoning), VISASQ, Treasure AI, LegalOn — all Tokyo/Japan.

Siblings: `../flipgate/` (found clause fabrication: AWQ +14.8pts hallucinations) and `../graphproof-qa/` (xgrammar integration already debugged there, incl. KV-cached constrained loop).
Prep context: `../../noeon-prep/`.

---

## Active project: FedProc-Constrained

Compile the FAR/DFARS registry (1,056 canonical IDs) into a decoding grammar so a small LLM cannot output a nonexistent clause number — then measure the real finding: how often the blocked fake turns into a real-but-wrong clause (substitution rate), and what the grammar costs in speed.

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

1. **Registry + grammars** (3d) — ✅ COMPLETE. 1,128 raw → 1,056 canonical IDs (checksummed vs flipgate); enum grammar compiles in 0.6s; input-span grammar builder; 16 tests green.
2. **Substitution measurement** (4d) — ✅ COMPLETE (60 prompts: 30 fake-topic, 15 near-miss, 15 obscure-real; Qwen2.5-1.5B):
   - Unconstrained: 82% fabrication [72%, 91%]
   - Enum grammar: 0% fabrication; the original '75% substitution' headline was an artefact (see README Correction, 2026-10-05)
   - Span grammar: malformed on ID-less inputs (empty-clause JSON — needs unknown-token fallback)
   - Post-hoc filter + retry: 77% fabrication (fixes 3/49 — barely helps)
   - Speed: enum 40.6 vs free 45.1 tok/s (~10% overhead)
3. **Release** (3d) — pending: repo push retry, HF dataset (prompts + per-item outputs), dev.to write-up.

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
