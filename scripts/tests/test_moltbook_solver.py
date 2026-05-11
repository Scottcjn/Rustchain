#!/usr/bin/env python3
"""
Unit tests for Moltbook Challenge Solver.
Bounty #1589 - Write a unit test for any untested function
"""

import pytest
import sys
import os
from pathlib import Path
import sqlite3
import tempfile

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

from moltbook_solver import (
    degarble,
    extract_numbers,
    solve_regex,
    _content_hash,
    is_content_unique,
    record_post,
    get_available_agents,
    get_agent_key,
    AGENTS,
)


class TestDegarble:
    """Tests for degarble() function."""

    def test_basic_garble_removal(self):
        result = degarble("A] lOoObS")
        assert "loobs" in result

    def test_special_char_stripping(self):
        result = degarble("ClAwS ExErT/ TwEnTy")
        assert "claws" in result and "exert" in result

    def test_whitespace_normalization(self):
        assert degarble("hello   world") == "hello world"

    def test_repeated_char_collapse(self):
        assert degarble("loooob") == "loob"

    def test_word_corrections(self):
        result = degarble("loobster notons")
        assert "lobster" in result and "newtons" in result


class TestExtractNumbers:
    """Tests for extract_numbers() function."""

    def test_integers(self):
        assert 5.0 in extract_numbers("I have 5 apples")

    def test_floats(self):
        assert 19.99 in extract_numbers("Price is 19.99")

    def test_word_numbers(self):
        assert 25.0 in extract_numbers("twenty five")

    def test_no_numbers(self):
        assert extract_numbers("hello world") == []

    def test_duplicate_prevention(self):
        nums = extract_numbers("5 and 5")
        assert nums.count(5.0) <= 1


class TestSolveRegex:
    """Tests for solve_regex() function."""

    def test_addition(self):
        answer, confidence = solve_regex("What is 5 + 3?")
        assert float(answer) == 8.0 and confidence >= 0.9

    def test_subtraction(self):
        answer, confidence = solve_regex("What is 10 - 4?")
        assert float(answer) == 6.0 and confidence >= 0.9

    def test_multiplication(self):
        answer, confidence = solve_regex("What is 6 * 7?")
        assert float(answer) == 42.0 and confidence >= 0.9

    def test_division(self):
        answer, confidence = solve_regex("What is 20 / 4?")
        assert abs(float(answer) - 5.0) < 0.01

    def test_no_match(self):
        answer, confidence = solve_regex("What is the capital of France?")
        assert answer is None and confidence == 0.0


class TestContentHash:
    """Tests for _content_hash() function."""

    def test_consistent_hash(self):
        hash1 = _content_hash("Test", "Content")
        hash2 = _content_hash("Test", "Content")
        assert hash1 == hash2

    def test_different_content(self):
        hash1 = _content_hash("Title", "Content 1")
        hash2 = _content_hash("Title", "Content 2")
        assert hash1 != hash2

    def test_empty_strings(self):
        hash1 = _content_hash("", "")
        assert len(hash1) == 16


class TestAgentFunctions:
    """Tests for agent functions."""

    def test_get_available_agents(self, monkeypatch):
        for config in AGENTS.values():
            monkeypatch.delenv(config["env"], raising=False)
        monkeypatch.setenv("MOLTBOOK_MSGOOGLETOGGLE_API_KEY", "test-token-msgoogletoggle")
        agents = get_available_agents()
        assert agents == ["msgoogletoggle"]

    def test_get_agent_key(self, monkeypatch):
        monkeypatch.setenv("MOLTBOOK_SOPHIA_API_KEY", "test-token-sophia")
        key = get_agent_key("sophia")
        assert key == "test-token-sophia"

    def test_get_agent_key_missing_env(self, monkeypatch):
        monkeypatch.delenv("MOLTBOOK_SOPHIA_API_KEY", raising=False)
        assert get_agent_key("sophia") is None

    def test_agents_have_required_fields(self):
        for agent_name, config in AGENTS.items():
            assert "env" in config and "persona" in config


class TestRecordPost:
    """Tests for record_post() function."""

    def test_record_post_creates_entry(self):
        import moltbook_solver
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            original_db = moltbook_solver.STATE_DB
            moltbook_solver.STATE_DB = tmp_path
            
            record_post("Test", "Content", "sophia", "test")
            
            conn = sqlite3.connect(str(tmp_path))
            cursor = conn.execute("SELECT COUNT(*) FROM post_hashes")
            count = cursor.fetchone()[0]
            conn.close()
            
            assert count >= 1
            moltbook_solver.STATE_DB = original_db
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
