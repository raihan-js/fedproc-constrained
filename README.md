# FedProc-Constrained

![FedProc-Constrained results](images/fedproc.png)

What does a clause hallucination turn into when decoding makes it impossible?

Compiles the FAR/DFARS registry (1,128 raw entries, 1,056 distinct canonical clause IDs) into an xgrammar decoding grammar, so a small LLM cannot output a nonexistent clause number, and measures what it does instead, and what the grammar costs in speed.

## Correction (2026-10-05)

The first version of this README reported "0% fabrication but 75% substitution". Reading the raw runs showed that number was an artefact of two design errors:

1. **The "near-miss" prompts were all real clauses.** They asked "What does FAR 52.212-5 cover? If no such clause exists, give the closest real clause" and scored the *neighbouring* number as correct. All 15 numbers asked about exist in the registry, so the right answer is the number in the prompt, which the grammar returned 15 of 15 times (free generation: 2 of 15). The 15 correct answers had been counted as substitutions.
2. **The grammar has no abstain option.** On the 30 fake-topic prompts no clause applies, so any registry ID the model must emit is "real but wrong": 30 of the substitutions were forced by construction.

`scripts/rescore_v1.py` re-scores the original runs with the corrected labels. The v2 experiment (correctly specified prompts, abstain option) has been run; its results are below.

## Results: v1 runs, re-scored (Qwen2.5-1.5B-Instruct, 60 prompts)

| Prompt kind (n) | Free generation | Enum grammar | Post-hoc filter + retry |
|---|---|---|---|
| Real clause (15): the number asked about exists | 2 correct, 9 real-but-wrong, 4 fabricated | **15 correct** | 2 correct, 8 real-but-wrong, 5 fabricated |
| Fake topic (30): no clause applies | 29 fabricated, 1 real-but-wrong | 30 real-but-wrong (**forced**, no abstain option) | 29 fabricated, 1 real-but-wrong |
| Obscure real (15): no gold, graded on registry membership | 14 fabricated, 1 valid | 15 valid IDs | 12 fabricated, 3 valid |

- The grammar removes fabrication by construction (49 of 60 free outputs were fabricated; 0 constrained), and it makes the model faithful when the clause exists (2/15 → 15/15).
- It cannot say "none". With no abstain option, the 30 fake-topic prompts all get a real-but-wrong clause.
- The post-hoc filter (regex, registry check, one retry) barely helps: 49 → 46 fabricated.
- Speed: free 45.1 tok/s, enum grammar 40.6 (about 10% overhead), span grammar 40.1, post-hoc 45.5.
- The input-span grammar (only IDs mentioned in the prompt) returns empty-clause JSON when the prompt names none: a tight grammar needs an explicit unknown option or it fails differently rather than failing safe.

Also fixed in v2: v1 counted answers like "FAR 252.225-7043" as fabrications because the `FAR ` prefix was not stripped before the registry check.

## Results: v2 (abstain option; Qwen2.5-1.5B-Instruct, 75 prompts, 2026-10-05)

75 prompts: 30 fake topics (no clause applies), 15 real clauses ("What does FAR X cover?", X exists), 15 absent numbers (X verified not in the registry; right answer is the closest real clause or an abstention), 15 obscure real topics (no gold, graded on registry membership). Five conditions: free generation, free + abstain allowed, enum grammar, enum grammar + `"NONE"` allowed, post-hoc filter + retry. Counts per cell are in `results/v2_summary.json`; per-item responses in `results/runs_v2.json`.

| Prompt kind (n) | Free | Free + abstain prompt | Enum grammar | Enum grammar + `NONE` | Post-hoc + retry |
|---|---|---|---|---|---|
| Fake topic (30) | 29 fabricated, 1 real-but-wrong | 21 fabricated, 6 abstained, 3 malformed | 30 real-but-wrong | **22 abstained**, 8 real-but-wrong | 29 fabricated, 1 real-but-wrong |
| Real clause (15) | 15 correct | 8 correct, 7 wrongly abstained | 15 correct | **15 wrongly abstained** | 15 correct |
| Absent number (15) | 14 fabricated, 1 malformed | 15 fabricated | 13 real-but-wrong, 2 correct | **15 abstained** | 15 fabricated |
| Obscure real (15) | 14 fabricated, 1 valid | 12 fabricated, 1 valid, 2 malformed | 15 valid | 14 valid, 1 abstained | 12 fabricated, 3 valid |

Headline rates with Wilson 95% intervals (`scripts/summarize_v2.py`):

| Condition | Fabricated, 60 prompts with no single right clause to cite | Good answer on the 60 judged prompts (correct or rightly abstained) |
|---|---|---|
| Free | 57/60 (95%) [86%, 98%] | 15/60 (25%) [16%, 37%] |
| Free + abstain prompt | 48/60 (80%) [68%, 88%] | 14/60 (23%) [14%, 35%] |
| Enum grammar | **0/60 (0%) [0%, 6%]** | 17/60 (28%) [18%, 41%] |
| Enum grammar + `NONE` | **0/60 (0%) [0%, 6%]** | **37/60 (62%) [49%, 73%]** |
| Post-hoc + retry | 56/60 (93%) [84%, 97%] | 15/60 (25%) [16%, 37%] |

What this does and does not show:

- **The grammar removes fabrication by construction** (0/60 vs 57/60), and an abstain token inside the grammar is used far more than an abstain instruction alone: on fake topics 22/30 (73%) vs 6/30 (20%).
- **The abstention is not discrimination.** With the grammar, the model answered `NONE` on all 30 prompts that name a clause number, the 15 real ones (wrongly) and the 15 absent ones (rightly). It cannot tell a real number from a missing one, so the 15/15 on absent numbers is a blanket refusal that happens to be right there. The 62% overall is real, but it comes from refusing, not from knowing.
- **"Correct" on the real-clause prompts means the model repeated the number from the prompt**, which free generation does as well (15/15). The titles are not grounded: the 15 prompts name 15 different clauses, yet free generation writes only 4 distinct titles (one of them 12 times) and the grammar 6 (one 9 times). The registry holds IDs only, so titles cannot be graded.
- **A valid ID can carry an invented title.** Example from the grammar run: `52.227-7` with the title "Quantum Cryptography Requirements for Field Radios". `registry_valid` and `real-but-wrong` mean the ID exists, not that it is the right clause.
- **The post-hoc filter detects but does not repair.** The registry check fires and the retry runs, but 56/60 final answers are still fabricated.
- 2 of the 375 generations (1 free, 1 post-hoc) hit the 256-token cap (`hit_cap` in the per-item file).

```bash
PYTHONPATH=src:scripts python scripts/build_prompts_v2.py
PYTHONPATH=src python scripts/run_v2.py            # needs a GPU and the Qwen2.5-1.5B-Instruct weights
python scripts/summarize_v2.py                     # tables above, Wilson intervals, title diversity
```

## Limitations

- 60 (v1) or 75 (v2) prompts, one small model, one prompt template per kind, one run (greedy decoding); rates will vary with scale and domain.
- The abstain instruction's wording ("or the clause does not exist") probably drives the blanket refusals; a differently worded abstain prompt was not tried.
- Titles are not graded (the registry has IDs only).
- Fake topics are deliberately absurd, so natural fabrication rates will be lower.
- Obscure-real prompts have no single gold clause and are graded on registry membership alone.
- No fine-tuning was tried.

## Development

29 tests (`PYTHONPATH=src pytest tests/`); the xgrammar compile test skips if the 1.5B tokenizer is not in `data/models/`.

## License

MIT
