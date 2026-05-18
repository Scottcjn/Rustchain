# SPDX-License-Identifier: MIT
from pathlib import Path
import re


SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rips"
    / "rustchain-core"
    / "src"
    / "anti_spoof"
    / "challenge_response.c"
)


def _source() -> str:
    return SOURCE_PATH.read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    match = re.search(rf"^[^\n]*\b{name}\([^)]*\) \{{.*?^}}", source, re.M | re.S)
    assert match is not None
    return match.group(0)


def _nonce_helper(source: str) -> str:
    if "fill_secure_nonce(" in source:
        return _function(source, "fill_secure_nonce")
    return _function(source, "fill_secure_random")


def test_challenge_nonce_uses_os_csprng_not_rand() -> None:
    source = _source()

    assert "rand(" not in source
    assert "srand(" not in source
    assert "getrandom(" in source
    assert "SecRandomCopyBytes(" in source or "arc4random_buf(" in source
    assert 'open("/dev/urandom", O_RDONLY)' in source or "#else\n    return -1;" in source


def test_linux_getrandom_result_is_checked_and_retried() -> None:
    helper = _nonce_helper(_source())

    assert "while (offset < len)" in helper
    assert "getrandom(buf + offset, len - offset, 0)" in helper or "getrandom(nonce + offset, len - offset, 0)" in helper
    assert "offset += (size_t)got" in helper or "offset += (size_t)n" in helper
    assert "errno == EINTR" in helper
    assert "(void)ret" not in helper


def test_unsupported_platform_uses_urandom_without_weak_fallback() -> None:
    helper = _nonce_helper(_source())
    fallback = helper.rsplit("#else", 1)[1]

    assert "return -1;" in fallback
    assert 'open("/dev/urandom", O_RDONLY)' in fallback or fallback.strip().startswith("return -1;\n#endif")
    assert "read_timebase()" not in fallback
    assert ">> (i * 8)" not in fallback


def test_nonce_failure_exits_before_returning_challenge() -> None:
    generate_challenge = _function(_source(), "generate_challenge")

    assert (
        "fill_secure_random(c.nonce, sizeof(c.nonce)) != 0" in generate_challenge
        or "fill_secure_nonce(c.nonce, sizeof(c.nonce)) != 0" in generate_challenge
    )
    assert "exit(1)" in generate_challenge or "exit(EXIT_FAILURE)" in generate_challenge
