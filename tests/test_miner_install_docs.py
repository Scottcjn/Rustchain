# SPDX-License-Identifier: MIT
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
MINING_HTML = ROOT / "docs" / "mining.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_readme_does_not_advertise_unpublished_miner_pypi_package():
    readme = read(README)

    assert "pip install rustchain-miner" not in readme
    assert "install-miner.sh | bash" in readme


def test_mining_page_uses_installed_miner_script_commands():
    html = read(MINING_HTML)

    assert "rustchain-miner --wallet" not in html
    assert "rustchain-attest --start" not in html
    assert "~/.rustchain/start.sh" in html
    assert "~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet" in html
