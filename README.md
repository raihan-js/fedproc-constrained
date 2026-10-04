# FedProc-Constrained

![FedProc-Constrained results](images/fedproc.png)

What does a clause hallucination turn into when decoding makes it impossible?

Compiles the FAR/DFARS registry (1,128 raw entries, 1,056 distinct canonical clause IDs) into a decoding grammar so a small LLM cannot output a nonexistent clause number — then measures the real finding: how often the blocked fake turns into a real-but-wrong clause (**substitution rate**), and what the grammar costs in speed.

## Results (60 prompts, Qwen2.5-1.5B-Instruct)

| Condition | Fabrication | Substitution | Correct | Speed |
|---|---|---|---|---|
| Unconstrained | 82% (49/60) | 8% | 8% | 45.1 tok/s |
| Enum grammar (full registry) | **0%** | **75% (45/60)** | 0% | 40.6 tok/s |
| Span grammar (input IDs only) | 0% | 25% | 0% | 40.1 tok/s |
| Post-hoc filter + retry | 77% (46/60) | 10% | 8% | 45.5 tok/s |

95% CIs: fabrication [72%, 91%]; substitution [64%, 86%]. "Correct" needs a known gold clause (only the 15 near-miss prompts have one); the remaining enum outputs are registry-valid on prompts with no gold (25%).

### By prompt kind (from `data/runs_full.json`)

| Prompt kind (n) | Unconstrained | Enum grammar |
|---|---|---|
| Fake topic (30): no correct clause exists | 29 fabricated, 1 substituted | 30 substituted |
| Near-miss (15): gold clause known | 5 correct, 4 substituted, 6 fabricated | **0 correct, 15 substituted** |
| Obscure real (15): no gold, graded on registry membership | 14 fabricated, 1 registry-valid | 15 registry-valid |

**Two things this table says that the headline hides.**

1. **The enum grammar has no abstain option.** On fake-topic prompts there is no right clause, so any registry ID the model must emit is a "substitution": 30 of the 45 substitutions are forced by construction, and "the model abstains" was never a testable outcome.
2. **On the 15 answerable prompts, correct fell from 5 to 0.** The constrained model lost the answers the unconstrained model got right. That is the measured part of the result, and it may reflect the grammar or a token-level issue (a Qwen tokenisation vs ID-trie misalignment was seen in GraphProof-QA) rather than something inherent to constraining; it needs a follow-up with an explicit "none" option before it is read as a general finding.

**Read it:** the grammar guarantees 0% fabrication *by construction*, which is not the result. What replaces it is: every fake-topic and near-miss prompt gets a real-but-wrong clause, but note the grammar has no abstain option, so for the 30 fake-topic prompts that is forced (see the breakdown below). The cheap post-hoc filter barely helps (retry fixes 3/49). Grammar overhead is ~10%.

Span grammar on inputs without registry IDs produces empty-clause JSON (`{"clause": ,"title": "..."}`) — a tight grammar needs an explicit unknown-token fallback, or it fails differently rather than failing safe.

## Status

Milestones 1–2 complete. See `AGENTS.md`.

## License

MIT
