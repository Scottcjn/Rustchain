import json
import sqlite3
import subprocess
import sys

import pytest

from node.agent_vanity_wallets import (
    AgentVanityError,
    generate_vanity_wallet,
    get_agent_vanity_wallet,
    list_agent_vanity_wallets,
    normalize_agent_name,
    register_agent_vanity_wallet,
)


FINGERPRINT = {
    "cpu": "IBM POWER8",
    "clock_skew_ppm": 18.4,
    "cache_signature": "l2:stable:l3:wide",
    "thermal_curve": [31.2, 34.8, 37.1],
}


def test_agent_name_normalization_and_reserved_names():
    assert normalize_agent_name("Claude_Code") == "claude-code"
    with pytest.raises(AgentVanityError, match="reserved"):
        normalize_agent_name("treasury")
    with pytest.raises(AgentVanityError, match="3_to_20"):
        normalize_agent_name("ab")


def test_vanity_wallet_is_deterministic_for_same_agent_and_hardware():
    first = generate_vanity_wallet("Sophia", FINGERPRINT)
    second = generate_vanity_wallet("sophia", dict(reversed(list(FINGERPRINT.items()))))

    assert first == second
    assert first.wallet.startswith("RTC-sophia-")
    assert len(first.wallet.rsplit("-", 1)[-1]) == 10


def test_vanity_constraints_mine_hash_prefix():
    wallet = generate_vanity_wallet("g4agent", FINGERPRINT, hash_prefix="00")

    assert wallet.wallet.startswith("RTC-g4agent-00")
    assert wallet.nonce > 0


def test_public_key_must_be_valid_ed25519_length():
    with pytest.raises(AgentVanityError, match="32_bytes"):
        generate_vanity_wallet("agentx", FINGERPRINT, public_key_hex="abcd")


def test_register_persists_wallet_and_is_idempotent():
    conn = sqlite3.connect(":memory:")

    created = register_agent_vanity_wallet(conn, "powerbot", FINGERPRINT, now_ts=123)
    loaded = get_agent_vanity_wallet(conn, "powerbot")
    repeated = register_agent_vanity_wallet(conn, "powerbot", FINGERPRINT, now_ts=456)

    assert loaded == created
    assert repeated == created
    assert list_agent_vanity_wallets(conn) == [created]


def test_registration_rejects_second_agent_on_same_hardware():
    conn = sqlite3.connect(":memory:")
    register_agent_vanity_wallet(conn, "agent-one", FINGERPRINT)

    with pytest.raises(AgentVanityError, match="hardware_already_bound"):
        register_agent_vanity_wallet(conn, "agent-two", FINGERPRINT)


def test_cli_generate_outputs_json():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "node.agent_vanity_wallets",
            "generate",
            "demo-agent",
            "--fingerprint",
            json.dumps(FINGERPRINT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["agent_name"] == "demo-agent"
    assert payload["wallet"].startswith("RTC-demo-agent-")

