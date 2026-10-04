"""Decoding grammars for FAR/DFARS clause citation.

Two grammars, both compiled with xgrammar:
  1. full_registry_grammar: any of the ~1.1k registry IDs is a valid
     citation. Guarantees 0% invented clause numbers by construction.
  2. input_span_grammar: only registry IDs that ALSO appear in the input
     text are valid. Tighter; tests whether narrowing helps or hurts.

Output shape enforced in both: {"clause": "<ID>", "title": "<text>"}.
The model must still choose WHICH clause (and its title) — the grammar
only restricts the ID to the registry. A real-but-wrong ID is a
substitution, which is the measured outcome (not a prevented one).
"""

import json
import re
import time

_CLAUSE_RE = re.compile(r"^\d{2,3}\.\d{3}(?:-\d+[a-z]?)?(?:\([a-z0-9]+\))*$", re.IGNORECASE)
_CLAUSE_FIND = re.compile(r"(\d{2,3}\.\d{3}(?:-\d+[a-z]?)?(?:\([a-z0-9]+\))*)", re.IGNORECASE)


def canonicalize(raw: str) -> str:
    """Strip FAR/DFARS prefixes and whitespace: 'DFARS 252.204-7012' -> '252.204-7012'."""
    s = raw.strip()
    s = re.sub(r"^(?:FAR|DFARS)\s+", "", s, flags=re.IGNORECASE)
    return s


def load_registry(path: str = "data/registry/far_registry.json") -> list[str]:
    with open(path, encoding="utf-8") as f:
        reg = json.load(f)
    canon = sorted({canonicalize(c) for c in reg})
    assert all(_CLAUSE_RE.match(c) for c in canon), "registry has malformed IDs"
    return canon


def _json_response_grammar(clause_alt: str) -> str:
    # Structural JSON wrapper; the clause ID slot is the constrained part.
    # Whitespace tolerated between tokens (Qwen space-merging).
    return (
        'root ::= " "* "{" " "* "\\"clause\\"" " "* ":" " "* '
        f'({clause_alt})'
        ' " "* "," " "* "\\"title\\"" " "* ":" " "* "\\"" [^"]* "\\"" " "* "}"\n'
    )


ABSTAIN = "NONE"


def full_registry_grammar(registry: list[str], allow_abstain: bool = False) -> tuple[str, float]:
    """EBNF allowing any registry ID. Returns (ebnf, build_time_s).

    With allow_abstain=True the sentinel "NONE" is also a valid clause value, so the model
    can say that no clause applies instead of being forced to emit some real ID (v1 had no
    such option, which forced a "substitution" on every prompt with no right answer).

    Note: build_time here is Python string assembly (~ms). The xgrammar
    compile time (trie build) is measured separately at first use.
    """
    t0 = time.time()
    ids = list(registry) + ([ABSTAIN] if allow_abstain else [])
    clause_alt = "|".join(f'"\\"{c}\\""' for c in ids)
    ebnf = _json_response_grammar(clause_alt)
    return ebnf, time.time() - t0


def input_span_grammar(registry: set[str], text: str) -> tuple[str, float]:
    """EBNF allowing only registry IDs mentioned in the input text."""
    t0 = time.time()
    mentioned = sorted({c for c in registry if c in text})
    clause_alt = "|".join(f'"\\"{c}\\""' for c in mentioned) if mentioned else '""'
    ebnf = _json_response_grammar(clause_alt)
    return ebnf, time.time() - t0


def extract_cited_ids(response: str) -> list[str]:
    """All FAR/DFARS-shaped numbers cited anywhere in free text."""
    return _CLAUSE_FIND.findall(response)


def base_number(clause_id: str) -> str:
    """Strip paragraph suffixes: 52.212-3(g) -> 52.212-3."""
    return re.sub(r"(\([a-z0-9]+\))*$", "", clause_id, flags=re.IGNORECASE)


def is_registry_id(clause_id: str, registry: set[str]) -> bool:
    """Membership with suffix-stripped fallback.

    A cited ID is valid iff it OR its base number is in the registry.
    Lenient side is deliberate: for a gate, blocking a valid sub-citation
    (false positive) is worse than missing a fabricated paragraph suffix.
    Documented; the strict variant (exact match only) is one flag away.
    """
    return clause_id in registry or base_number(clause_id) in registry


def extract_json_clause(response: str) -> str | None:
    """Parse the {"clause": "<ID>", ...} response shape (fences tolerated)."""
    text = response.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    clause = obj.get("clause")
    return clause if isinstance(clause, str) else None
