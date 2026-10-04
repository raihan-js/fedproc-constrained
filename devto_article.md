![fedproc-constrained results](https://raw.githubusercontent.com/raihan-js/fedproc-constrained/HEAD/images/fedproc.png)

# What Happens When Decoding Makes Hallucination Impossible? Substitution.

*Blocking a fake FAR clause doesn't produce truth. It produces a real-but-wrong clause 75% of the time.*

---

## The Setup

FlipGate (my last project) found that quantized LLMs fabricate FAR/DFARS clause numbers — AWQ invented 34 new ones (p=0.001). The obvious fix: compile the registry (1,128 raw entries, 1,056 distinct canonical clause IDs) into a decoding grammar so the model *cannot* emit a nonexistent number.

That guarantee is true by construction — which makes it worthless as a finding. The real question is what the blocked fake turns into. Three hypotheses: the model abstains, it finds the right clause, or it substitutes a real-but-wrong one. (The enum grammar I built has no "none" option, so abstaining was never actually possible; I only noticed when breaking the results down by prompt kind.)

## The Experiment

Qwen2.5-1.5B-Instruct, 60 fabrication-eliciting prompts (fake topics, near-miss numbers, obscure real topics), four conditions:

| Condition | Fabrication | Substitution | Speed |
|---|---|---|---|
| Unconstrained | 82% (49/60) | 8% | 45.1 tok/s |
| Enum grammar (full registry) | **0%** | **75% (45/60)** | 40.6 tok/s |
| Span grammar (input IDs only) | 0% | 25% | 40.1 tok/s |
| Post-hoc filter + retry | 77% (46/60) | 10% | 45.5 tok/s |

95% CIs: fabrication [72%, 91%]; substitution [64%, 86%].

### By prompt kind (from `data/runs_full.json`)

| Prompt kind (n) | Unconstrained | Enum grammar |
|---|---|---|
| Fake topic (30): no correct clause exists | 29 fabricated, 1 substituted | 30 substituted |
| Near-miss (15): gold clause known | 5 correct, 4 substituted, 6 fabricated | **0 correct, 15 substituted** |
| Obscure real (15): no gold, graded on registry membership | 14 fabricated, 1 registry-valid | 15 registry-valid |

**Two things this table says that the headline hides.**

1. **The enum grammar has no abstain option.** On fake-topic prompts there is no right clause, so any registry ID the model must emit is a "substitution": 30 of the 45 substitutions are forced by construction, and "the model abstains" was never a testable outcome.
2. **On the 15 answerable prompts, correct fell from 5 to 0.** The constrained model lost the answers the unconstrained model got right. That is the measured part of the result, and it may reflect the grammar or a token-level issue (a Qwen tokenisation vs ID-trie misalignment was seen in GraphProof-QA) rather than something inherent to constraining; it needs a follow-up with an explicit "none" option before it is read as a general finding.

## Reading It Honestly

- The 0% is by construction. Never lead with it.
- The 75% substitution rate needs reading with the breakdown above: 30 of the 45 are forced because the grammar offers no way to say "none". What is measured is that constrained output passes a registry check while being wrong, and that on the 15 answerable prompts correct fell from 5 to 0. For compliance use cases a wrong-but-valid ID is arguably worse than an obvious fabrication, because it passes a registry check.
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
- No abstain option in the enum grammar, so substitution is forced on fake-topic prompts; re-run with an explicit "none" before drawing conclusions about abstention.
- The near-miss drop from 5 correct to 0 may be a grammar/tokenisation artefact; not investigated.

---

*Repo: github.com/raihan-js/fedproc-constrained · Data: huggingface.co/datasets/raihan-js/fedproc-constrained-results · 16 tests green.*
