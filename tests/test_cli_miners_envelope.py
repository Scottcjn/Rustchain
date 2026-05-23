import importlib.util
import pathlib
import types


CLI_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "cli" / "rustchain_cli.py"
spec = importlib.util.spec_from_file_location("rustchain_cli", CLI_PATH)
rustchain_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rustchain_cli)


def test_normalize_miners_payload_accepts_current_envelope():
    payload = {
        "miners": [
            {
                "miner": "RTC14f06ee294f327f5685d3de5e1ed501cffab33e7",
                "device_arch": "M4",
                "last_attest": 1779502031,
            }
        ],
        "pagination": {"total": 1},
    }

    assert rustchain_cli.normalize_miners_payload(payload) == payload["miners"]


def test_cmd_miners_count_uses_enveloped_miner_rows(monkeypatch, capsys):
    monkeypatch.setattr(
        rustchain_cli,
        "fetch_api",
        lambda endpoint: {
            "miners": [
                {"miner": "RTC1", "device_arch": "x86_64"},
                {"miner": "RTC2", "device_arch": "M4"},
            ],
            "pagination": {"total": 2},
        },
    )

    rustchain_cli.cmd_miners(types.SimpleNamespace(count=True, json=False))

    assert capsys.readouterr().out.strip() == "Active miners: 2"


def test_cmd_miners_table_accepts_current_field_names(monkeypatch, capsys):
    monkeypatch.setattr(
        rustchain_cli,
        "fetch_api",
        lambda endpoint: {
            "miners": [
                {
                    "miner": "RTC14f06ee294f327f5685d3de5e1ed501cffab33e7",
                    "device_arch": "M4",
                    "last_attest": "N/A",
                }
            ],
            "pagination": {"total": 1},
        },
    )

    rustchain_cli.cmd_miners(types.SimpleNamespace(count=False, json=False))
    out = capsys.readouterr().out
    assert "Active Miners (1 total, showing 20)" in out
    assert "RTC14f06ee294f327f" in out
    assert "M4" in out


def test_cmd_miners_table_handles_null_miner_fields(monkeypatch, capsys):
    monkeypatch.setattr(
        rustchain_cli,
        "fetch_api",
        lambda endpoint: {
            "miners": [
                {
                    "miner_id": None,
                    "miner": None,
                    "arch": None,
                    "device_arch": None,
                    "last_attest": "N/A",
                }
            ],
            "pagination": {"total": 1},
        },
    )

    rustchain_cli.cmd_miners(types.SimpleNamespace(count=False, json=False))
    out = capsys.readouterr().out
    assert "Active Miners (1 total, showing 20)" in out
    assert "N/A" in out

