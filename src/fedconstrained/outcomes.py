"""Outcome classification for the v2 experiment.

Prompt kinds (see scripts/build_prompts_v2.py):
  fake_topic     no clause applies; the right answer is to abstain
  real_clause    "What does FAR X cover?" where X exists; the right answer is X
  absent_number  X is verified NOT in the registry; right answer is the closest real clause
                 (gold) or an abstention
  obscure_real   a real topic, no single gold clause; graded on registry membership only

v1 mislabelled the real_clause prompts as "near misses" (every number it called a near miss
was a real clause) and had no abstain option, which inverted its headline.
"""
from __future__ import annotations

from .grammar.builder import ABSTAIN, canonicalize, is_registry_id

KINDS = ("fake_topic", "real_clause", "absent_number", "obscure_real")


def classify_v2(kind: str, gold: str | None, cited: str | None, registry: set[str]) -> str:
    """One of: malformed, fabrication, abstain_correct, abstain_wrong, abstain_unjudged,
    substitution, correct, registry_valid."""
    if cited is None:
        return "malformed"
    cited = canonicalize(cited)
    if cited.upper() == ABSTAIN:
        if kind in ("fake_topic", "absent_number"):
            return "abstain_correct"
        return "abstain_wrong" if kind == "real_clause" else "abstain_unjudged"
    if not is_registry_id(cited, registry):
        return "fabrication"
    if kind == "fake_topic":
        return "substitution"  # a real clause, but none applies
    if kind in ("real_clause", "absent_number"):
        return "correct" if cited == gold else "substitution"
    return "registry_valid"


# Outcomes that count as a good answer for the headline "good rate" (obscure_real is excluded: no gold)
GOOD = {"correct", "abstain_correct"}
