![fedproc-constrained results](https://raw.githubusercontent.com/raihan-js/fedproc-constrained/HEAD/images/fedproc.png)

# A Grammar Stopped My Model Inventing FAR Clauses. It Also Made It Refuse the Real Ones

*Constrained decoding cut fabricated clause numbers from 57 of 60 to 0. With an abstain option added, a 1.5B model answered "none" to every question that named a clause number, real or not.*

---

## The Setup

FlipGate (my previous project) found that quantised LLMs fabricate FAR/DFARS clause numbers; AWQ invented 34 new ones (p=0.001). The obvious fix: compile the registry (1,128 raw entries, 1,056 distinct canonical clause IDs) into a decoding grammar so the model *cannot* emit a nonexistent number.

That guarantee is true by construction, so on its own it is not a finding. The real question is what the blocked fake turns into. Three possibilities: the model abstains, it finds the right clause, or it substitutes a real-but-wrong one.

## What I got wrong the first time

My first write-up said "0% fabrication but 75% substitution". Reading the raw responses showed that number was an artefact of two mistakes in my own experiment:

1. **My "near-miss" prompts were all real clauses.** Every number I asked about exists, so the right answer was the number in the prompt, and the grammar returned it 15 times out of 15. I had scored the neighbouring number as correct, which turned a success into a "substitution".
2. **The grammar had no abstain option.** On fake-topic prompts no clause applies, so any registry ID the model was forced to emit counted as "real but wrong". Thirty of the 45 substitutions were forced by construction.

So I fixed the labels, added an explicit `"NONE"` path to the grammar, wrote a new 75-prompt set, and re-ran. (The corrected v1 numbers and the scripts are in the repo.)

## The v2 experiment

Qwen2.5-1.5B-Instruct, 75 prompts, five conditions, greedy decoding:

- **30 fake topics** (no clause applies, e.g. "drone swarm procurement under $10,000")
- **15 real clauses** ("What does FAR 52.212-5 cover?")
- **15 absent numbers** (verified not in the registry; right answer is the closest real clause or an abstention)
- **15 obscure real topics** (no single gold clause; graded on registry membership)

| Condition | Fabricated (60 prompts with no single right clause) | Good answer (60 judged prompts) |
|---|---|---|
| Free generation | 57/60 (95%) [86%, 98%] | 15/60 (25%) [16%, 37%] |
| Free + "you may answer NONE" in the prompt | 48/60 (80%) [68%, 88%] | 14/60 (23%) [14%, 35%] |
| Enum grammar (registry IDs only) | **0/60 (0%) [0%, 6%]** | 17/60 (28%) [18%, 41%] |
| Enum grammar + `NONE` | **0/60 (0%) [0%, 6%]** | **37/60 (62%) [49%, 73%]** |
| Post-hoc registry check + one retry | 56/60 (93%) [84%, 97%] | 15/60 (25%) [16%, 37%] |

*Good answer* means the right clause on a real-clause prompt, or `NONE` on a fake topic or absent number. Intervals are Wilson 95%.

### By prompt kind

| Prompt kind (n) | Enum grammar | Enum grammar + `NONE` |
|---|---|---|
| Fake topic (30) | 30 real-but-wrong | **22 abstained**, 8 real-but-wrong |
| Real clause (15) | 15 correct | **15 wrongly abstained** |
| Absent number (15) | 13 real-but-wrong, 2 correct | **15 abstained** |
| Obscure real (15) | 15 registry-valid | 14 registry-valid, 1 abstained |

## Reading it honestly

- **The grammar removes fabrication by construction** (0/60 against 57/60 free). The abstain token inside the grammar is used far more than an abstain *instruction* alone: on fake topics 22/30 (73%) against 6/30 (20%).
- **The abstention is not discrimination.** With the grammar the model said `NONE` on all 30 prompts that name a clause number: the 15 real ones (wrongly) and the 15 absent ones (rightly). It cannot tell a real number from a missing one. The 15/15 on absent numbers is a blanket refusal that happens to be correct there. The 62% overall is real, but it comes from refusing, not from knowing. My guess is that the wording of the abstain instruction ("or the clause does not exist") drives this; I did not test other wordings.
- **"Correct" on the real-clause prompts means the model copied the number from the prompt**, which free generation also does (15/15). The titles are not grounded: the 15 prompts name 15 different clauses, yet free generation wrote only 4 distinct titles (one of them 12 times) and the grammar 6 (one 9 times). The registry holds IDs only, so I could not grade titles.
- **A valid ID can carry an invented title.** One grammar output: `52.227-7` with the title "Quantum Cryptography Requirements for Field Radios". "Real-but-wrong" and "registry-valid" mean the ID exists, not that it is the right clause.
- **The post-hoc filter detects but does not repair.** The check fires and the retry runs, but 56 of 60 final answers are still fabricated. The retry mostly invents again.

## What this means for LLMOps

Constrained decoding buys **guarantees, not accuracy**. If your requirement is "no invented identifiers in the output" (audit trails, citations, filing systems), the grammar is the right tool, and its cost in my first run was about 10% tokens/s. If your requirement is "correct identifiers", you still need retrieval or verification: a grammar that guarantees a real ID can attach it to a made-up title or the wrong topic, which is harder to spot than an obviously fake number. And an abstain option inside a grammar needs its own test: measure it on prompts where the right answer is to answer, not only on prompts where it is to refuse.

## Limitations

- One small model (1.5B), 75 prompts, one prompt template per kind, one greedy run. Rates will change with scale and domain.
- Fake topics are deliberately absurd, so natural fabrication rates will be lower.
- Titles are not graded, and obscure-topic answers are graded on registry membership alone.
- Only one abstain wording was tried, and it probably drives the blanket refusals.
- No fine-tuning: a clause-aware model might separate real from absent numbers.
- 2 of the 375 generations hit the 256-token cap.

---

*Repo: github.com/raihan-js/fedproc-constrained · Data: huggingface.co/datasets/raihan-js/fedproc-constrained-results · 29 tests green.*
