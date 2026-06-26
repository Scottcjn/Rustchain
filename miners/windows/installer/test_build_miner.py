import importlib.util
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("build_miner.py")
    spec = importlib.util.spec_from_file_location("build_miner_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_passes_timeout_to_pyinstaller(monkeypatch, tmp_path):
    module = load_module()
    project_dir = tmp_path / "installer"
    src_dir = project_dir / "src"
    dist_dir = project_dir / "dist"
    src_dir.mkdir(parents=True)
    entry_point = src_dir / "rustchain_windows_miner.py"
    entry_point.write_text("print('miner')\n", encoding="utf-8")
    (dist_dir).mkdir()
    exe_path = dist_dir / "RustChainMiner.exe"

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        exe_path.write_bytes(b"exe")

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(module, "PROJECT_DIR", project_dir)
    monkeypatch.setattr(module, "SRC_DIR", src_dir)
    monkeypatch.setattr(module, "ENTRY_POINT", entry_point)
    monkeypatch.setattr(module, "ICON_FILE", project_dir / "assets" / "rustchain.ico")
    monkeypatch.setattr(module, "DIST_DIR", dist_dir)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.build()

    assert calls
    assert calls[0][1]["cwd"] == str(project_dir)
    assert calls[0][1]["timeout"] == module.BUILD_TIMEOUT_SECONDS


def test_build_exits_cleanly_on_pyinstaller_timeout(monkeypatch, tmp_path):
    module = load_module()
    project_dir = tmp_path / "installer"
    src_dir = project_dir / "src"
    src_dir.mkdir(parents=True)
    entry_point = src_dir / "rustchain_windows_miner.py"
    entry_point.write_text("print('miner')\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        raise module.subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(module, "PROJECT_DIR", project_dir)
    monkeypatch.setattr(module, "SRC_DIR", src_dir)
    monkeypatch.setattr(module, "ENTRY_POINT", entry_point)
    monkeypatch.setattr(module, "ICON_FILE", project_dir / "assets" / "rustchain.ico")
    monkeypatch.setattr(module, "DIST_DIR", project_dir / "dist")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    try:
        module.build()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected timeout SystemExit")
