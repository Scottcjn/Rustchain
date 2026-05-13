# SPDX-License-Identifier: Apache-2.0
from pathlib import Path


SOURCE = Path("rips/rustchain-core/src/anti_spoof/challenge_response.c")


def test_c_challenge_nonce_uses_os_csprng():
    source = SOURCE.read_text(encoding="utf-8")

    assert "rand(" not in source
    assert "srand(" not in source
    assert "fill_secure_random(c.nonce, sizeof(c.nonce))" in source
    assert "getrandom(" in source
    assert "SecRandomCopyBytes(" in source
    assert 'open("/dev/urandom", O_RDONLY)' in source


def test_c_challenge_nonce_failure_is_fatal():
    source = SOURCE.read_text(encoding="utf-8")

    assert "Failed to generate secure challenge nonce" in source
    assert "exit(1)" in source
