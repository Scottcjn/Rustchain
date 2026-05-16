import importlib.util
import sys
from pathlib import Path


def load_updater():
    module_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "actions"
        / "mining-status-badge"
        / "update_badge.py"
    )
    spec = importlib.util.spec_from_file_location("mining_status_badge_updater", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_appends_badge_block_when_markers_are_missing(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = load_updater()
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n")
    monkeypatch.setattr(sys, "argv", ["update_badge.py", str(readme)])
    monkeypatch.setenv("WALLET", "wallet-123")
    monkeypatch.setenv("STYLE", "flat")

    module.main()

    text = readme.read_text()
    assert "# Project" in text
    assert "## Mining Status" in text
    assert "<!-- rustchain-mining-badge-start -->" in text
    assert "https://rustchain.org/api/badge/wallet-123&style=flat" in text
    assert "Updated" in capsys.readouterr().out


def test_main_replaces_existing_badge_block(monkeypatch, tmp_path):
    module = load_updater()
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Project",
                "<!-- rustchain-mining-badge-start -->",
                "old badge",
                "<!-- rustchain-mining-badge-end -->",
                "after",
            ]
        )
    )
    monkeypatch.setattr(sys, "argv", ["update_badge.py", str(readme)])
    monkeypatch.setenv("WALLET", "fresh-wallet")
    monkeypatch.setenv("STYLE", "plastic")

    module.main()

    text = readme.read_text()
    assert "old badge" not in text
    assert "after" in text
    assert "https://rustchain.org/api/badge/fresh-wallet&style=plastic" in text
    assert text.count("rustchain-mining-badge-start") == 1


def test_main_exits_when_readme_is_missing(monkeypatch, tmp_path, capsys):
    module = load_updater()
    missing = tmp_path / "missing.md"
    monkeypatch.setattr(sys, "argv", ["update_badge.py", str(missing)])

    try:
        module.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    assert f"README not found: {missing}" in capsys.readouterr().out
