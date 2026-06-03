from pathlib import Path


def test_rust_miner_readme_explains_dry_run_behavior():
    readme = Path("rustchain-miner/README.md").read_text(encoding="utf-8")

    assert "--dry-run" in readme
    assert "preflight checks" in readme
    assert "hardware fingerprint" in readme
    assert "actual mining" in readme


def test_clawrtc_docs_do_not_recommend_unsupported_mine_dry_run():
    docs = "\n".join(
        [
            Path("docs/FAQ.md").read_text(encoding="utf-8"),
            Path("docs/UPGRADE_MIGRATION_GUIDE.md").read_text(encoding="utf-8"),
        ]
    )

    assert "clawrtc mine --dry-run" not in docs
    assert "install-miner.sh --dry-run" in docs
