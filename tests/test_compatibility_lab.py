# SPDX-License-Identifier: MIT
import copy
import json
import urllib.parse

import pytest

from compatibility_lab import (
    ContractError,
    load_contract,
    probe_base_url,
    validate_fixtures,
)
from compatibility_lab.cli import main
from compatibility_lab.contract import (
    DEFAULT_CONTRACT_PATH,
    _NoRedirect,
    fixture_directory,
    validate_fixture,
)
from compatibility_lab.docs import (
    check_documented_routes,
    check_local_links,
    configured_link_files,
    generate_reference,
    generated_reference_path,
    stale_reference_error,
)


class FakeResponse:
    def __init__(
        self, body, status=200, content_type="application/json; charset=utf-8"
    ):
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._payload = json.dumps(body).encode("utf-8")
        self.closed = False

    def read(self, size=-1):
        return self._payload if size < 0 else self._payload[:size]

    def close(self):
        self.closed = True


@pytest.fixture(scope="module")
def contract():
    return load_contract(DEFAULT_CONTRACT_PATH)


def _fixture_body(contract, name):
    path = fixture_directory(contract) / name
    return json.loads(path.read_text(encoding="utf-8"))["body"]


def test_canonical_contract_has_only_the_four_get_routes(contract):
    assert set(contract["paths"]) == {
        "/health",
        "/epoch",
        "/api/miners",
        "/wallet/balance",
    }
    assert contract["security"] == []
    for path_item in contract["paths"].values():
        assert set(path_item) == {"get"}
        assert path_item["get"]["security"] == []


def test_probe_transport_refuses_redirects():
    handler = _NoRedirect()
    assert (
        handler.redirect_request(None, None, 302, "Found", {}, "https://other.example")
        is None
    )


def test_all_declared_offline_fixtures_validate(contract):
    results = validate_fixtures(contract)
    assert len(results) == 8
    assert {name: errors for name, errors in results.items() if errors} == {}


def test_fixture_validation_rejects_response_drift(contract):
    fixture_path = fixture_directory(contract) / "miners-200.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["body"]["pagination"]["count"] = "2"
    fixture["body"]["unexpected"] = True

    errors = validate_fixture(contract, fixture, "mutated-miners.json")

    assert any("$.body.pagination.count: expected integer" in error for error in errors)
    assert any("$.body.unexpected: additional property" in error for error in errors)


def test_probe_constructs_only_get_requests_without_credentials_or_bodies(contract):
    requests = []
    responses = {
        "/health": _fixture_body(contract, "health-200.json"),
        "/epoch": _fixture_body(contract, "epoch-200.json"),
        "/api/miners": _fixture_body(contract, "miners-200.json"),
        "/wallet/balance": _fixture_body(contract, "wallet-balance-200.json"),
    }

    def fake_open(request, timeout):
        requests.append((request, timeout))
        path = urllib.parse.urlsplit(request.full_url).path
        assert path.startswith("/rustchain/")
        route = path.removeprefix("/rustchain")
        return FakeResponse(responses[route])

    results = probe_base_url(
        contract,
        "https://node.example/rustchain",
        miner_id="fixture-wallet",
        timeout=3,
        fetcher=fake_open,
    )

    assert len(results) == 4
    assert all(result.valid for result in results)
    assert all(result.status == 200 for result in results)
    assert all(request.get_method() == "GET" for request, _ in requests)
    assert all(request.data is None for request, _ in requests)
    assert all(timeout == 3 for _, timeout in requests)
    assert all(
        "authorization" not in {key.lower() for key, _ in request.header_items()}
        for request, _ in requests
    )
    assert requests[2][0].full_url.endswith("/api/miners?limit=2")
    assert requests[3][0].full_url.endswith("/wallet/balance?miner_id=fixture-wallet")


@pytest.mark.parametrize(
    "base_url, miner_id",
    [
        ("https://user:secret@node.example", "fixture-wallet"),
        ("file:///tmp/node", "fixture-wallet"),
        ("https://node.example", "bad wallet id"),
    ],
)
def test_probe_rejects_credentials_unsafe_schemes_and_bad_ids(
    contract, base_url, miner_id
):
    with pytest.raises(ContractError):
        probe_base_url(
            contract, base_url, miner_id=miner_id, fetcher=lambda *_a, **_k: None
        )


def test_probe_fails_closed_when_transport_returns_no_response(contract):
    results = probe_base_url(
        contract,
        "https://node.example",
        fetcher=lambda *_args, **_kwargs: None,
    )

    assert len(results) == 4
    assert all(not result.valid for result in results)
    assert all(result.errors == ("request returned no response",) for result in results)


def test_generated_reference_and_configured_links_are_current(contract):
    path = generated_reference_path(contract)
    assert path.read_text(encoding="utf-8") == generate_reference(contract)
    assert stale_reference_error(contract) is None
    assert check_local_links(configured_link_files(contract)) == []
    assert check_documented_routes(contract) == []


def test_link_checker_reports_missing_target_and_anchor(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("# Existing Heading\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        "[missing](missing.md)\n[bad anchor](target.md#not-there)\n",
        encoding="utf-8",
    )

    errors = check_local_links([source], repository_root=tmp_path)

    assert any("missing local link target" in error for error in errors)
    assert any("missing local link anchor" in error for error in errors)


def test_route_checker_rejects_documented_unregistered_api(tmp_path, contract):
    source = tmp_path / "node.py"
    source.write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/api/miners', methods=['GET'])\n"
        "def miners():\n"
        "    return {}\n",
        encoding="utf-8",
    )
    docs = tmp_path / "README.md"
    docs.write_text(
        "[miners](https://rustchain.org/api/miners)\n"
        "[unsupported](https://rustchain.org/api/tokenomics)\n"
        "[unsupported relative](/api/tokenomics)\n",
        encoding="utf-8",
    )
    test_contract = copy.deepcopy(contract)
    config = test_contract["x-rustchain-compatibility"]["documentation_route_check"]
    config["files"] = ["README.md"]
    config["authoritative_sources"] = ["node.py"]

    errors = check_documented_routes(test_contract, repository_root=tmp_path)

    assert len(errors) == 2
    assert all("/api/tokenomics" in error for error in errors)
    assert ":2:" in errors[0]
    assert ":3:" in errors[1]


def test_ci_command_is_fully_offline_and_passes(contract, monkeypatch, capsys):
    def fail_if_networked(*_args, **_kwargs):
        raise AssertionError("CI command must not access the network")

    monkeypatch.setattr("urllib.request.urlopen", fail_if_networked)

    assert main(["ci"]) == 0
    output = capsys.readouterr().out
    assert "offline fixtures valid" in output
    assert "generated API contract reference is current" in output


def test_repository_commands_fail_clearly_without_a_checkout(
    contract, tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "compatibility_lab.cli.PACKAGE_ROOT", tmp_path / "installed-package"
    )

    assert main(["ci"]) == 2
    assert "repository checkout required" in capsys.readouterr().err
