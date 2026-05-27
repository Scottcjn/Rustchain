from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_beginner_clawrtc_install_docs_use_python_module_pip():
    docs = [
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "README_ES.md",
        ROOT / "README_JA.md",
        ROOT / "README_ZH.md",
        ROOT / "BCOS.md",
        ROOT / "docs" / "CLAIMS_GUIDE.md",
        ROOT / "docs" / "FAQ.md",
        ROOT / "docs" / "i18n" / "ko" / "QUICKSTART.md",
        ROOT / "docs" / "MULTISIG_WALLET_GUIDE.md",
        ROOT / "docs" / "RUSTCHAIN_DEVELOPER_TUTORIAL.md",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "python3 -m pip install clawrtc" in text
        assert "pip install clawrtc" not in text.replace(
            "python3 -m pip install clawrtc", ""
        )
