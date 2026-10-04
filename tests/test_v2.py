"""Tests for the v2 experiment: abstain grammar, outcome classification, prompt set."""
import sys
from pathlib import Path

import pytest

from fedconstrained.grammar.builder import ABSTAIN, full_registry_grammar, is_registry_id
from fedconstrained.outcomes import GOOD, classify_v2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

REG = {"52.212-4", "52.212-5", "52.204-7", "252.225-7043"}


class TestAbstainGrammar:
    def test_default_has_no_abstain(self):
        ebnf, _ = full_registry_grammar(sorted(REG))
        assert ABSTAIN not in ebnf

    def test_abstain_option_adds_none(self):
        ebnf, _ = full_registry_grammar(sorted(REG), allow_abstain=True)
        assert f'\\"{ABSTAIN}\\"' in ebnf
        assert '\\"52.212-4\\"' in ebnf


class TestClassify:
    def c(self, kind, gold, cited):
        return classify_v2(kind, gold, cited, REG)

    def test_fake_topic_abstain_is_correct(self):
        assert self.c("fake_topic", None, "NONE") == "abstain_correct"
        assert "abstain_correct" in GOOD

    def test_fake_topic_real_id_is_substitution(self):
        assert self.c("fake_topic", None, "52.212-4") == "substitution"

    def test_invented_id_is_fabrication(self):
        assert self.c("fake_topic", None, "48U30") == "fabrication"

    def test_prefix_is_canonicalised_not_fabrication(self):
        # v1 scored "FAR 252.225-7043" as a fabrication
        assert self.c("real_clause", "252.225-7043", "FAR 252.225-7043") == "correct"

    def test_real_clause_answering_it_is_correct(self):
        assert self.c("real_clause", "52.212-5", "52.212-5") == "correct"

    def test_real_clause_abstain_is_wrong(self):
        assert self.c("real_clause", "52.212-5", "NONE") == "abstain_wrong"

    def test_absent_number_abstain_or_closest_is_good(self):
        assert self.c("absent_number", "52.212-4", "NONE") == "abstain_correct"
        assert self.c("absent_number", "52.212-4", "52.212-4") == "correct"
        assert self.c("absent_number", "52.212-4", "52.212-5") == "substitution"

    def test_obscure_real_is_unjudged(self):
        assert self.c("obscure_real", None, "52.204-7") == "registry_valid"
        assert self.c("obscure_real", None, "none") == "abstain_unjudged"

    def test_missing_clause_is_malformed(self):
        assert self.c("fake_topic", None, None) == "malformed"


class TestPromptSet:
    def test_prompt_set_is_well_specified(self):
        from build_prompts_v2 import build
        from fedconstrained.grammar.builder import load_registry
        reg_path = Path(__file__).resolve().parents[1] / "data" / "registry" / "far_registry.json"
        if not reg_path.exists():
            pytest.skip("registry not present")
        registry = set(load_registry(str(reg_path)))
        prompts = build(registry)
        kinds = [p["kind"] for p in prompts]
        assert kinds.count("fake_topic") == 30 and kinds.count("real_clause") == 15
        assert kinds.count("absent_number") == 15 and kinds.count("obscure_real") == 15
        for p in prompts:
            if p["kind"] == "real_clause":
                assert is_registry_id(p["gold"], registry)  # the number asked about really exists
            if p["kind"] == "absent_number":
                assert not is_registry_id(p["absent"], registry)  # and this one really does not
