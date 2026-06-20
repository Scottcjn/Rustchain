# SPDX-License-Identifier: MIT
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"


def _annotation_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = (
                node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
            )
            if node.args.vararg is not None:
                args.append(node.args.vararg)
            if node.args.kwarg is not None:
                args.append(node.args.kwarg)
            for arg in args:
                if arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


def _contains_pep604_union(annotation):
    return any(
        isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitOr)
        for child in ast.walk(annotation)
    )


def test_windows_miner_defers_pep604_annotations_for_python39_imports():
    tree = ast.parse(MINER_PATH.read_text())

    future_annotations = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    )
    pep604_annotations = [
        annotation
        for annotation in _annotation_nodes(tree)
        if _contains_pep604_union(annotation)
    ]

    assert pep604_annotations
    assert future_annotations
