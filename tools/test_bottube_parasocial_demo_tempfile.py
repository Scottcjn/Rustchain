from pathlib import Path


def test_bottube_demo_does_not_use_mktemp():
    source = Path(__file__).with_name("bottube_parasocial_demo.py").read_text(encoding="utf-8")

    assert "tempfile.mktemp" not in source
    assert "tempfile.NamedTemporaryFile" in source
