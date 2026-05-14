# SPDX-License-Identifier: MIT
"""Regression checks for challenge-response nonce generation."""

from pathlib import Path
import re


SOURCE = Path(__file__).with_name("challenge_response.c")
TEXT = SOURCE.read_text(encoding="utf-8")


def test_no_libc_prng_for_challenge_nonce() -> None:
    assert not re.search(r"\b(?:srand|rand)\s*\(", TEXT)


def test_os_csprng_paths_are_available() -> None:
    assert "getrandom(" in TEXT
    assert "SecRandomCopyBytes" in TEXT
    assert '"/dev/urandom"' in TEXT


def test_nonce_generation_fails_closed() -> None:
    assert "fill_secure_random(c.nonce, sizeof(c.nonce))" in TEXT
    assert "exit(EXIT_FAILURE)" in TEXT


if __name__ == "__main__":
    test_no_libc_prng_for_challenge_nonce()
    test_os_csprng_paths_are_available()
    test_nonce_generation_fails_closed()
