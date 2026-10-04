# FedProc-Constrained

![FedProc-Constrained results](images/fedproc.png)

What does a clause hallucination turn into when decoding makes it impossible?

Compiles the FAR/DFARS registry (1,128 raw entries, 1,056 distinct canonical clause IDs) into a decoding grammar so a small LLM cannot output a nonexistent clause number — then measures the real finding: how often the blocked fake turns into a real-but-wrong clause (**substitution rate**), and what the grammar costs in speed.

## Results (60 prompts, Qwen2.5-1.5B-Instruct)

| Condition | Fabrication | Substitution | Correct | Speed |
|---|---|---|---|---|
| Unconstrained | 82% (49/60) | 8% | 8% | 45.1 tok/s |
| Enum grammar (full registry) | **0%** | **75% (45/60)** | 8% | 40.6 tok/s |
| Span grammar (input IDs only) | 0% | 25% | 0% | 40.1 tok/s |
| Post-hoc filter + retry | 77% (46/60) | 10% | 8% | 45.5 tok/s |

95% CIs: fabrication [72%, 91%]; substitution [64%, 86%].

**Read it:** the grammar guarantees 0% fabrication *by construction* — that is not the win. The win is measuring what replaces it: three-quarters of blocked fakes become real-but-wrong clauses. The cheap post-hoc filter barely helps (retry fixes 3/49). Grammar overhead is ~10%.

Span grammar on inputs without registry IDs produces empty-clause JSON (`{"clause": ,"title": "..."}`) — a tight grammar needs an explicit unknown-token fallback, or it fails differently rather than failing safe.

## Status

Milestones 1–2 complete. See `AGENTS.md`.

## License

MIT
