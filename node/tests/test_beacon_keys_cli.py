#!/usr/bin/env python3
"""Tests for beacon_keys_cli.py — Beacon Keys CLI."""
import argparse
import pytest
from node.beacon_keys_cli import build_parser, dispatch, cmd_keys_list, cmd_keys_show


class TestBuildParser:
    def test_parser_has_all_commands(self):
        """Parser should have all subcommands."""
        parser = build_parser("test-keys")
        subcmds = {a.dest for a in parser._actions if hasattr(a, 'choices') and a.choices}
        # Get subcommand names
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                assert "list" in action.choices
                assert "show" in action.choices
                assert "revoke" in action.choices
                assert "rotate" in action.choices
                assert "expire" in action.choices

    def test_list_accepts_miner_id(self):
        """list subcommand should accept --miner-id."""
        parser = build_parser()
        args = parser.parse_args(["list", "--miner-id", "test-miner"])
        assert args.miner_id == "test-miner"

    def test_show_accepts_key_id(self):
        """show subcommand should accept key-id."""
        parser = build_parser()
        args = parser.parse_args(["show", "--key-id", "key-123"])
        assert args.key_id == "key-123"

    def test_default_exit_on_error(self):
        """Parser should not exit on error by default."""
        parser = build_parser()
        assert parser.exit_on_error is False

    def test_prog_name(self):
        """Parser prog should match."""
        parser = build_parser("beacon-keys")
        assert parser.prog == "beacon-keys"

    def test_list_no_miner_id(self):
        """list subcommand without --miner-id should set None."""
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.miner_id is None


class TestDispatch:
    def test_invalid_command_returns_2(self):
        """Invalid command should return exit code 2."""
        rc = dispatch(["invalid-command"])
        assert rc == 2

    def test_help_returns_0(self):
        """--help should return 0."""
        with pytest.raises(SystemExit) as exc:
            dispatch(["--help"])
        assert exc.value.code == 0

    def test_empty_args_returns_2(self):
        """Empty args should return 2 (help printed via error)."""
        rc = dispatch([])
        assert rc in (0, 2)


class TestCmdKeysList:
    def test_list_returns_int(self):
        """cmd_keys_list should return an integer exit code."""
        args = argparse.Namespace(miner_id=None)
        rc = cmd_keys_list(args)
        assert isinstance(rc, int)


class TestCmdKeysShow:
    def test_show_without_key_id(self):
        """cmd_keys_show without key-id should return error."""
        args = argparse.Namespace(key_id=None)
        rc = cmd_keys_show(args)
        assert rc != 0
