import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_verifier():
    module_path = Path(__file__).resolve().parents[1] / "tier3" / "verify_tier3.py"
    spec = importlib.util.spec_from_file_location("tier3_verify", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_command_returns_true_when_command_succeeds(monkeypatch, capsys):
    module = load_verifier()
    calls = []

    def fake_run(command, capture_output):
        calls.append((command, capture_output))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.run_command(["python", "-V"], "Version Check") is True
    assert calls == [(["python", "-V"], False)]
    assert "Version Check - PASSED" in capsys.readouterr().out


def test_run_command_returns_false_when_command_fails(monkeypatch, capsys):
    module = load_verifier()
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, capture_output: SimpleNamespace(returncode=1),
    )

    assert module.run_command(["python", "missing.py"], "Missing Script") is False
    assert "Missing Script - FAILED" in capsys.readouterr().out


def test_main_returns_success_when_commands_pass_and_artifacts_exist(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_verifier()
    script_dir = tmp_path / "tier3"
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "run.json").write_text("{}")
    monkeypatch.setattr(module, "__file__", str(script_dir / "verify_tier3.py"))
    monkeypatch.setattr(module, "run_command", lambda command, description: True)

    assert module.main() == 0

    output = capsys.readouterr().out
    assert "Tests Passed: 3/3" in output
    assert "run.json" in output
    assert "ALL VERIFICATIONS PASSED" in output


def test_main_returns_failure_when_a_command_fails(monkeypatch, tmp_path, capsys):
    module = load_verifier()
    script_dir = tmp_path / "tier3"
    artifact_dir = script_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "run.json").write_text("{}")
    monkeypatch.setattr(module, "__file__", str(script_dir / "verify_tier3.py"))
    outcomes = iter([True, False])
    monkeypatch.setattr(
        module,
        "run_command",
        lambda command, description: next(outcomes),
    )

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "Tests Passed: 2/3" in output
    assert "SOME VERIFICATIONS FAILED" in output


def test_main_returns_failure_when_artifact_directory_is_missing(monkeypatch, tmp_path):
    module = load_verifier()
    script_dir = tmp_path / "tier3"
    script_dir.mkdir()
    monkeypatch.setattr(module, "__file__", str(script_dir / "verify_tier3.py"))
    monkeypatch.setattr(module, "run_command", lambda command, description: True)

    assert module.main() == 1
