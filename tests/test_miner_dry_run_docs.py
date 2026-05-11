from pathlib import Path


def test_rust_miner_readme_explains_dry_run_behavior():
    readme = Path("rustchain-miner/README.md").read_text(encoding="utf-8")

    assert "--dry-run" in readme
    assert "preflight checks" in readme
    assert "hardware fingerprint" in readme
    assert "without actual mining" in readme
