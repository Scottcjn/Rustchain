"""
tests/test_moltbook_beacon_migration.py

Test suite validating AgentFolio ↔ Beacon Dual-Layer Trust Integration (Bounty #2890):
1. Migration importer metadata resolution & hardware fingerprinting
2. Substrate Beacon ID minting & SATP trust profile generation
3. MCP agentfolio_beacon_lookup tool functionality & offline/untrusted handling
"""

import json
import pytest
from tools.moltbook_migrate.migrate import (
    sanitize_handle,
    collect_hardware_fingerprint,
    fetch_moltbook_profile,
    mint_beacon_id,
    create_satp_trust_profile,
    execute_migration
)
from tools.moltbook_migrate.agentfolio_beacon_mcp import (
    lookup_agent,
    compute_satp_trust
)


def test_sanitize_handle():
    assert sanitize_handle("@agent_alpha") == "agent_alpha"
    assert sanitize_handle("agent.beta") == "agent.beta"
    assert sanitize_handle("@special#agent!") == "special_agent_"


def test_collect_hardware_fingerprint():
    fp = collect_hardware_fingerprint()
    assert "architecture" in fp
    assert "os" in fp
    assert "substrate_hash" in fp
    assert len(fp["substrate_hash"]) == 64


def test_fetch_moltbook_profile():
    profile = fetch_moltbook_profile("test_agent")
    assert profile["handle"] == "test_agent"
    assert "karma_history" in profile
    assert profile["karma_history"]["historical_karma"] > 0
    assert profile["follower_count"] > 0


def test_mint_beacon_id():
    sub_hash = "abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890def"
    bid = mint_beacon_id("solana_oracle", sub_hash)
    assert bid.startswith("bcn_solana_")
    assert len(bid) == len("bcn_solana_") + 8


def test_create_satp_trust_profile():
    profile = {
        "karma_history": {"historical_karma": 8000},
        "follower_count": 1500
    }
    satp = create_satp_trust_profile("bcn_test_123", profile, "subhash")
    assert satp["satp_pubkey"].startswith("SATP")
    assert satp["trust_score"] >= 70.0
    assert satp["provenance_anchored"] is True


def test_execute_migration_end_to_end(tmp_path):
    receipt_file = tmp_path / "receipt.json"
    receipt = execute_migration("@test_runner", str(receipt_file))
    assert receipt["status"] == "success"
    assert receipt["agent"]["handle"] == "test_runner"
    assert receipt["beacon"]["registered"] is True
    assert receipt["migration_duration_seconds"] < 10.0
    assert receipt_file.exists()


def test_mcp_lookup_agent_known():
    res = lookup_agent("bcn_zen2b6f")
    assert res["found"] is True
    assert res["beacon_id"] == "bcn_zen2b6f"
    assert "provenance_layer" in res
    assert "trust_layer_satp" in res
    assert res["trust_layer_satp"]["trust_score"] > 0.0


def test_mcp_lookup_unknown_fallback():
    res = lookup_agent("bcn_custom_migrated_12345678")
    assert res["found"] is True
    assert res["beacon_id"] == "bcn_custom_migrated_12345678"
    assert res["provenance_layer"]["protocol"] == "RustChain OpenClaw Beacon v1"
