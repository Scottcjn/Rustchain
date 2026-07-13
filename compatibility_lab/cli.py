# SPDX-License-Identifier: MIT
"""Command-line interface for the RustChain Compatibility Lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

from .contract import (
    DEFAULT_CONTRACT_PATH,
    PACKAGE_ROOT,
    ContractError,
    load_contract,
    probe_base_url,
    validate_fixtures,
)
from .docs import (
    check_documented_routes,
    check_local_links,
    configured_link_files,
    stale_reference_error,
    write_reference,
)


def _load(path: str) -> Optional[Mapping]:
    try:
        return load_contract(Path(path))
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return None


def _validate_command(contract: Mapping, fixtures: Optional[str]) -> int:
    fixture_path = Path(fixtures) if fixtures else None
    results = validate_fixtures(contract, fixture_path)
    failures = [(name, error) for name, errors in results.items() for error in errors]
    if failures:
        for name, error in failures:
            print(f"{name}: {error}", file=sys.stderr)
        return 1
    print(f"contract valid; {len(results)} offline fixtures valid")
    return 0


def _discover_repository_root(raw_root: Optional[str]) -> Optional[Path]:
    candidates = [Path(raw_root)] if raw_root else [Path.cwd(), PACKAGE_ROOT.parent]
    for candidate in candidates:
        root = candidate.resolve()
        if (root / "compatibility_lab" / "read_only_api.openapi.json").is_file() and (
            root / "pyproject.toml"
        ).is_file():
            return root
    return None


def _require_repository_root(raw_root: Optional[str]) -> Optional[Path]:
    root = _discover_repository_root(raw_root)
    if root is None:
        print(
            "repository checkout required; run from the RustChain root or pass --repo-root",
            file=sys.stderr,
        )
    return root


def _generate_docs_command(
    contract: Mapping, check: bool, repository_root: Path
) -> int:
    if check:
        error = stale_reference_error(contract, repository_root)
        if error:
            print(error, file=sys.stderr)
            return 1
        print("generated API contract reference is current")
        return 0
    path = write_reference(contract, repository_root)
    print(f"generated {path.relative_to(repository_root)}")
    return 0


def _check_links_command(
    contract: Mapping, raw_paths: Sequence[str], repository_root: Path
) -> int:
    files = (
        [Path(path).resolve() for path in raw_paths]
        if raw_paths
        else configured_link_files(contract, repository_root)
    )
    errors = check_local_links(files, repository_root)
    if not raw_paths:
        errors.extend(check_documented_routes(contract, repository_root))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"{len(files)} Markdown files have valid local links")
    if not raw_paths:
        print("configured API route claims are registered by the authoritative node")
    return 0


def _probe_command(
    contract: Mapping, base_url: str, miner_id: str, timeout: float
) -> int:
    try:
        results = probe_base_url(contract, base_url, miner_id=miner_id, timeout=timeout)
    except ContractError as exc:
        print(f"probe configuration error: {exc}", file=sys.stderr)
        return 2
    failed = False
    for result in results:
        status = str(result.status) if result.status is not None else "network-error"
        if result.valid:
            print(f"PASS {result.operation_id} [{status}] {result.url}")
        else:
            failed = True
            print(
                f"FAIL {result.operation_id} [{status}] {result.url}", file=sys.stderr
            )
            for error in result.errors:
                print(f"  {error}", file=sys.stderr)
    return 1 if failed else 0


def _ci_command(contract: Mapping, repository_root: Path) -> int:
    failed = False
    if _validate_command(contract, None):
        failed = True
    if _generate_docs_command(contract, check=True, repository_root=repository_root):
        failed = True
    if _check_links_command(contract, [], repository_root):
        failed = True
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rustchain-compat",
        description="Validate and safely probe RustChain's canonical read-only API contract.",
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT_PATH),
        help="OpenAPI 3.1 JSON contract path",
    )
    parser.add_argument(
        "--repo-root",
        help="RustChain checkout root for docs, link checks, and the ci command",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="validate the contract and offline fixtures"
    )
    validate.add_argument("--fixtures", help="override the fixture directory")

    probe = subparsers.add_parser(
        "probe", help="opt in to GET-only live endpoint probes"
    )
    probe.add_argument("base_url", help="HTTP(S) node base URL without credentials")
    probe.add_argument("--miner-id", default="compatibility-probe")
    probe.add_argument("--timeout", type=float, default=5.0)

    generate = subparsers.add_parser(
        "generate-docs", help="generate or check the checked-in contract reference"
    )
    generate.add_argument(
        "--check", action="store_true", help="fail instead of writing if stale"
    )

    links = subparsers.add_parser(
        "check-links", help="check local links in contract documentation"
    )
    links.add_argument(
        "paths", nargs="*", help="Markdown files; defaults to contract configuration"
    )

    subparsers.add_parser("ci", help="run every offline compatibility and docs check")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    contract = _load(args.contract)
    if contract is None:
        return 1
    if args.command == "validate":
        return _validate_command(contract, args.fixtures)
    if args.command == "probe":
        return _probe_command(contract, args.base_url, args.miner_id, args.timeout)
    repository_root = _require_repository_root(args.repo_root)
    if repository_root is None:
        return 2
    if args.command == "generate-docs":
        return _generate_docs_command(contract, args.check, repository_root)
    if args.command == "check-links":
        return _check_links_command(contract, args.paths, repository_root)
    if args.command == "ci":
        return _ci_command(contract, repository_root)
    return 2
