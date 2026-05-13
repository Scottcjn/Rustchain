import argparse
import json
import time
from pathlib import Path

from node import beacon_keys_cli
from node.beacon_identity import init_identity_tables, _upsert_key


def _seed_key(db_path: Path, agent_id="bcn_testagent", revoked=False, last_seen=None):
    now = time.time()
    init_identity_tables(str(db_path))
    _upsert_key(
        {
            "agent_id": agent_id,
            "pubkey_hex": "aa" * 32,
            "first_seen": now - 86400,
            "last_seen": now if last_seen is None else last_seen,
            "rotation_count": 2,
            "previous_key": "bb" * 32,
            "revoked": revoked,
            "revoked_at": now if revoked else None,
            "revoked_reason": "compromised" if revoked else None,
        },
        str(db_path),
    )


def test_list_json_outputs_seeded_keys(tmp_path, capsys):
    db = tmp_path / "beacon.db"
    _seed_key(db)

    rc = beacon_keys_cli.cmd_keys_list(
        argparse.Namespace(all=False, json=True, ttl=30 * 86400, db=str(db))
    )

    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["agent_id"] == "bcn_testagent"
    assert rows[0]["rotation_count"] == 2


def test_show_missing_key_returns_error(tmp_path, capsys):
    db = tmp_path / "beacon.db"
    init_identity_tables(str(db))

    rc = beacon_keys_cli.cmd_keys_show(
        argparse.Namespace(agent_id="missing", json=False, ttl=30 * 86400, db=str(db))
    )

    assert rc == 1
    assert "Key not found: missing" in capsys.readouterr().err


def test_revoke_command_marks_key_revoked(tmp_path, capsys):
    db = tmp_path / "beacon.db"
    _seed_key(db)

    rc = beacon_keys_cli.cmd_keys_revoke(
        argparse.Namespace(agent_id="bcn_testagent", reason="lost", db=str(db))
    )

    assert rc == 0
    assert "revoked" in capsys.readouterr().out.lower()
    info = beacon_keys_cli.get_key_info("bcn_testagent", db_path=str(db))
    assert info["is_revoked"] is True
    assert info["revoked_reason"] == "lost"


def test_expire_dry_run_reports_old_key_without_deleting(tmp_path, capsys):
    db = tmp_path / "beacon.db"
    _seed_key(db, last_seen=time.time() - 10_000)

    rc = beacon_keys_cli.cmd_keys_expire(
        argparse.Namespace(ttl=1, dry_run=True, db=str(db))
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "Would remove 1 expired key" in out
    assert beacon_keys_cli.get_key_info("bcn_testagent", db_path=str(db)) is not None


def test_dispatch_uses_parser_and_command_db(tmp_path, capsys):
    db = tmp_path / "beacon.db"
    _seed_key(db)

    rc = beacon_keys_cli.dispatch(["--db", str(db), "show", "bcn_testagent", "--json"])

    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["agent_id"] == "bcn_testagent"
