# What Happens When Decoding Makes Hallucination Impossible? Substitution.

*Blocking a fake FAR clause doesn't produce truth. It produces a real-but-wrong clause 75% of the time.*

---

## The Setup

FlipGate (my last project) found that quantized LLMs fabricate FAR/DFARS clause numbers — AWQ invented 34 new ones (p=0.001). The obvious fix: compile the 1,056-clause registry into a decoding grammar so the model *cannot* emit a nonexistent number.

That guarantee is true by construction — which makes it worthless as a finding. The real question is what the blocked fake turns into. Three hypotheses: the model abstains, it finds the right clause, or it substitutes a real-but-wrong one.

## The Experiment

Qwen2.5-1.5B-Instruct, 60 fabrication-eliciting prompts (fake topics, near-miss numbers, obscure real topics), four conditions:

| Condition | Fabrication | Substitution | Speed |
|---|---|---|---|
| Unconstrained | 82% (49/60) | 8% | 45.1 tok/s |
| Enum grammar (full registry) | **0%** | **75% (45/60)** | 40.6 tok/s |
| Span grammar (input IDs only) | 0% | 25% | 40.1 tok/s |
| Post-hoc filter + retry | 77% (46/60) | 10% | 45.5 tok/s |

95% CIs: fabrication [72%, 91%]; substitution [64%, 86%].

## Reading It Honestly

- The 0% is by construction. Never lead with it.
- The 75% substitution rate is the result: constrained models don't become truthful, they become *plausibly wrong* — real numbers, wrong answers. For compliance use cases, that's arguably worse than obvious fabrications, because it passes a registry check.
- The cheap post-hoc filter (regex + check + one retry) barely helps: 49→46 fabrications. The retry just invents again.
- Grammar overhead is ~10% tokens/s. Cheap.
- Span grammars on inputs without registry IDs emit empty-clause JSON (`{"clause": ,"title": ...}`) — tight grammars need an explicit unknown-token fallback, or they fail differently rather than failing safe.

## What This Means for LLMOps

Constrained decoding buys **guarantees, not accuracy**. If your threat model is "no invented identifiers in output" (audit trails, citations, filing systems), the grammar is the right tool and costs 10%. If your threat model is "correct identifiers," you still need retrieval, verification, or a human — the grammar just upgraded your hallucinations from detectable to sneaky.

## Limitations

- 60 prompts, single small model; substitution rate will vary with scale and domain.
- Fake topics are deliberately absurd; natural fabrication rates will be lower.
- Correctness judged only where gold exists (near-miss); obscure topics graded on registry membership alone.
- No fine-tuning tried — a clause-aware model might substitute less (or more confidently).

---

*Repo: github.com/raihan-js/fedproc-constrained · Data: huggingface.co/datasets/raihan-js/fedproc-constrained-results · 16 tests green.*
