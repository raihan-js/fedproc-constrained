# FedProc-Constrained

What does a clause hallucination turn into when decoding makes it impossible?

Compiles the 1,032-clause FAR/DFARS registry into a decoding grammar so a small LLM cannot output a nonexistent clause number — then measures the real finding: how often the blocked fake turns into a real-but-wrong clause (**substitution rate**), and what the grammar costs in speed.

## Status

Milestone 1 (registry + grammars) complete. See `AGENTS.md`.

## License

MIT
