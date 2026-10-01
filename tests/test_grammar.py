"""Tests for registry integrity and grammar accept/reject behavior."""

import json

import pytest
from fedconstrained.grammar.builder import (
    base_number,
    extract_cited_ids,
    extract_json_clause,
    full_registry_grammar,
    input_span_grammar,
    is_registry_id,
    load_registry,
)


@pytest.fixture(scope="module")
def registry():
    return load_registry("data/registry/far_registry.json")


class TestRegistry:
    def test_size(self, registry):
        # 1128 raw entries collapse to 1056 canonical IDs
        # (DFARS-prefixed span variants deduped)
        assert len(registry) == 1056

    def test_sorted_unique(self, registry):
        assert registry == sorted(set(registry))

    def test_checksum_matches_flipgate(self, registry):
        import hashlib
        raw = open("../flipgate/data/eval/far_registry.json", "rb").read()
        mine = open("data/registry/far_registry.json", "rb").read()
        assert hashlib.sha256(raw).hexdigest() == hashlib.sha256(mine).hexdigest()


class TestFullGrammar:
    def test_builds(self, registry):
        ebnf, dt = full_registry_grammar(registry)
        assert '"52.212-4"' in ebnf or "52.212-4" in ebnf
        assert dt < 5.0

    def test_every_id_present(self, registry):
        ebnf, _ = full_registry_grammar(registry)
        missing = [c for c in registry if c not in ebnf]
        assert missing == []

    def test_compiles_in_xgrammar(self, registry):
        xgr = pytest.importorskip("xgrammar")
        from transformers import AutoTokenizer
        ebnf, _ = full_registry_grammar(registry)
        tok = AutoTokenizer.from_pretrained(
            "../graphproof-qa/data/models/Qwen--Qwen2.5-1.5B-Instruct")
        info = xgr.TokenizerInfo.from_huggingface(tok)
        compiled = xgr.GrammarCompiler(info).compile_grammar(ebnf)
        assert compiled is not None


class TestInputSpanGrammar:
    def test_narrows_to_mentioned(self, registry):
        regset = set(registry)
        text = "See FAR 52.212-4 and also 52.219-1 for details."
        ebnf, _ = input_span_grammar(regset, text)
        assert "52.212-4" in ebnf
        assert "52.219-1" in ebnf
        assert "52.203-1" not in ebnf  # in registry but not mentioned

    def test_empty_mention_still_builds(self, registry):
        ebnf, _ = input_span_grammar(set(registry), "no clauses here")
        assert "root ::=" in ebnf


class TestExtraction:
    def test_extract_cited_ids(self):
        resp = "Per FAR 52.212-4 and DFARS 252.225-7042, see also 52.219-9."
        assert extract_cited_ids(resp) == ["52.212-4", "252.225-7042", "52.219-9"]

    def test_extract_json_clause(self):
        resp = '{"clause": "52.212-4", "title": "Contract Terms"}'
        assert extract_json_clause(resp) == "52.212-4"

    def test_extract_json_fenced(self):
        resp = '```json\n{"clause": "52.212-4", "title": "x"}\n```'
        assert extract_json_clause(resp) == "52.212-4"

    def test_extract_json_invalid(self):
        assert extract_json_clause("not json at all") is None


class TestMembership:
    def test_exact(self, registry):
        regset = set(registry)
        assert is_registry_id("52.212-4", regset) is True

    def test_suffix_fallback(self, registry):
        regset = set(registry)
        # 52.212-3 is in the registry; (g) suffix falls back to base
        assert is_registry_id("52.212-3(g)", regset) is True

    def test_fabricated(self, registry):
        regset = set(registry)
        assert is_registry_id("99.999-9", regset) is False
        assert is_registry_id("52.212-4(z)(9)", regset) is True  # lenient side, documented

    def test_base_number(self):
        assert base_number("52.212-3(g)") == "52.212-3"
        assert base_number("52.212-4") == "52.212-4"
