import importlib.util
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace


def load_witness_cli():
    witness_dir = Path(__file__).resolve().parents[1] / "witness"
    sys.path.insert(0, str(witness_dir))
    try:
        sys.modules.pop("witness_cli", None)
        spec = importlib.util.spec_from_file_location(
            "witness_cli",
            witness_dir / "witness_cli.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(witness_dir))


def test_main_without_command_prints_help_and_returns_error(monkeypatch, capsys):
    module = load_witness_cli()
    monkeypatch.setattr(sys, "argv", ["rustchain-witness"])

    assert module.main() == 1

    captured = capsys.readouterr()
    assert "usage: rustchain-witness" in captured.out
    assert "{write,read,verify,info}" in captured.out


def test_cmd_write_loads_json_list_and_uses_selected_media_size(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_witness_cli()
    source = tmp_path / "witnesses.json"
    source.write_text('[{"epoch": 42, "miners": []}]')
    captured_call = {}

    def fake_write(witnesses, output_path, image_size):
        captured_call["epochs"] = [witness.epoch for witness in witnesses]
        captured_call["output_path"] = output_path
        captured_call["image_size"] = image_size
        return True, "written"

    monkeypatch.setattr(module, "write_witnesses_to_image", fake_write)
    args = Namespace(
        from_json=str(source),
        epoch=1,
        output="witness.zip",
        format="zip",
    )

    assert module.cmd_write(args) == 0

    assert captured_call == {
        "epochs": [42],
        "output_path": "witness.zip",
        "image_size": module.ZIP_DISK_SIZE,
    }
    assert "written" in capsys.readouterr().out


def test_cmd_verify_passes_node_url_and_returns_failure(monkeypatch, tmp_path, capsys):
    module = load_witness_cli()
    source = tmp_path / "witness.json"
    source.write_text('{"epoch": 9, "miners": []}')
    captured_call = {}

    def fake_verify(witness, node_url):
        captured_call["epoch"] = witness.epoch
        captured_call["node_url"] = node_url
        return False, "invalid witness"

    monkeypatch.setattr(module, "verify_witness", fake_verify)
    args = Namespace(file=str(source), node="https://node.example")

    assert module.cmd_verify(args) == 1

    assert captured_call == {
        "epoch": 9,
        "node_url": "https://node.example",
    }
    assert "invalid witness" in capsys.readouterr().out


def test_cmd_read_prints_witness_summaries(monkeypatch, capsys):
    module = load_witness_cli()
    witnesses = [
        SimpleNamespace(epoch=7, miners=[object(), object()], settlement_hash="abcdef1234567890ff"),
        SimpleNamespace(epoch=8, miners=[], settlement_hash="0123456789abcdefff"),
    ]
    monkeypatch.setattr(module, "read_witnesses_from_image", lambda path: witnesses)

    assert module.cmd_read(Namespace(input="witness.img")) == 0

    captured = capsys.readouterr()
    assert "Found 2 epoch witnesses" in captured.out
    assert "Epoch 7 | 2 miners | Settlement: abcdef1234567890..." in captured.out
    assert "Epoch 8 | 0 miners | Settlement: 0123456789abcdef..." in captured.out
