# SPDX-License-Identifier: MIT

from pathlib import Path
import re


DOCS_WITH_PUBLIC_RUSTCHAIN_EXAMPLES = [
    Path("README.md"),
    Path("docs/API.md"),
    Path("docs/README.md"),
    Path("docs/zh-CN/README.md"),
]


def test_public_rustchain_curl_examples_keep_tls_verification_enabled():
    insecure_examples = []

    for doc_path in DOCS_WITH_PUBLIC_RUSTCHAIN_EXAMPLES:
        for line_number, line in enumerate(doc_path.read_text(encoding="utf-8").splitlines(), 1):
            if "curl" not in line or "https://rustchain.org" not in line:
                continue
            if re.search(r"\s-[A-Za-z]*k[A-Za-z]*\b", line):
                insecure_examples.append(f"{doc_path}:{line_number}: {line.strip()}")

    assert not insecure_examples, "\n".join(insecure_examples)


def test_public_rustchain_python_examples_keep_tls_verification_enabled():
    insecure_examples = []

    for doc_path in DOCS_WITH_PUBLIC_RUSTCHAIN_EXAMPLES:
        lines = doc_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "https://rustchain.org" not in line:
                continue
            request_block = "\n".join(lines[index : index + 8])
            if "verify=False" in request_block:
                insecure_examples.append(f"{doc_path}:{index + 1}: {line.strip()}")

    assert not insecure_examples, "\n".join(insecure_examples)
