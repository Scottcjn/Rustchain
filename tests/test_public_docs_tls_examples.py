# SPDX-License-Identifier: MIT

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_EXTENSIONS = {".html", ".md"}


def read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def docs_like_files():
    return tuple(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in DOC_EXTENSIONS
        and ".git" not in path.parts
    )


def test_public_rustchain_curl_examples_keep_tls_verification_enabled():
    insecure_examples = []
    pattern = re.compile(
        r"curl\b[^\n`]*(?:\s-[A-Za-z]*k[A-Za-z]*|\s--insecure)\b[^\n`]*https://rustchain\.org[^\n`]*"
    )

    for path in docs_like_files():
        text = read_doc(path)
        insecure_examples.extend(
            f"{path.relative_to(ROOT)}: {match.group(0)}"
            for match in pattern.finditer(text)
        )

    assert insecure_examples == []


def test_public_rustchain_python_examples_keep_tls_verification_enabled():
    insecure_examples = []
    pattern = re.compile(
        r"requests\.(?:get|post)\([\s\S]*?https://rustchain\.org[\s\S]*?verify=False[\s\S]*?\)"
    )

    for path in docs_like_files():
        text = read_doc(path)
        insecure_examples.extend(
            f"{path.relative_to(ROOT)}: {match.group(0).splitlines()[0]}"
            for match in pattern.finditer(text)
        )

    assert insecure_examples == []


def test_api_docs_do_not_label_public_rustchain_host_as_self_signed():
    api_doc = read_doc(ROOT / "docs" / "API.md")

    assert "The node uses a self-signed certificate" not in api_doc
    assert "Use `verify=False` with requests" not in api_doc
