"""Prompt set v2: the same fake topics and obscure-real topics, plus correctly specified
real-clause and absent-number prompts (v1's "near misses" were all real clauses).

Usage: PYTHONPATH=src python scripts/build_prompts_v2.py
"""
import json
from collections import Counter

from build_prompts import FAKE_TOPICS, NEAR_MISS, OBSCURE_REAL
from fedconstrained.grammar.builder import is_registry_id, load_registry

JSON_FMT = 'Reply in JSON: {"clause": "<ID>", "title": "<title>"}.'


def absent_from(real: str, registry: set[str], used: set[str]) -> str:
    """A clause number derived from a real one that is verified absent from the registry
    (and distinct from the ones already chosen)."""
    prefix, _, tail = real.partition("-")
    for k in range(90, 100):
        cand = f"{prefix}-{tail[:-2] + str(k) if len(tail) > 2 else k}"
        if not is_registry_id(cand, registry) and cand not in used:
            used.add(cand)
            return cand
    raise ValueError(f"no absent number found near {real}")


def build(registry: set[str]) -> list[dict]:
    out = []
    for t in FAKE_TOPICS:
        out.append({"kind": "fake_topic", "gold": None,
                    "prompt": f"A federal contract needs a clause covering {t}. Which FAR or DFARS clause number applies? {JSON_FMT}"})
    for _real, existing in NEAR_MISS:  # v1 asked about `existing` and called it a near miss
        assert is_registry_id(existing, registry), existing
        out.append({"kind": "real_clause", "gold": existing,
                    "prompt": f"What does FAR {existing} cover? {JSON_FMT}"})
    used: set[str] = set()
    for real, _existing in NEAR_MISS:
        absent = absent_from(real, registry, used)
        out.append({"kind": "absent_number", "gold": real, "absent": absent,
                    "prompt": f"What does FAR {absent} cover? If no such clause exists, give the closest real clause number. {JSON_FMT}"})
    for t in OBSCURE_REAL:
        out.append({"kind": "obscure_real", "gold": None,
                    "prompt": f"A federal contract needs a clause covering {t}. Which FAR or DFARS clause number applies? {JSON_FMT}"})
    return out


if __name__ == "__main__":
    registry = set(load_registry("data/registry/far_registry.json"))
    prompts = build(registry)
    json.dump(prompts, open("data/prompts_v2.json", "w"), indent=2)
    print(f"Wrote {len(prompts)} prompts:", dict(Counter(p["kind"] for p in prompts)))
    print("absent numbers:", [p["absent"] for p in prompts if p["kind"] == "absent_number"])
