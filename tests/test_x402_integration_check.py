# SPDX-License-Identifier: Apache-2.0

import json
import subprocess

from tools import x402_integration_check as check

EXPECTED_ENDPOINTS = {
    ("GET", "https://bottube.ai/api/x402/status"),
    ("GET", "https://bottube.ai/api/premium/videos"),
    ("GET", "https://bottube.ai/api/premium/analytics/sophia-elya"),
    ("GET", "https://bottube.ai/api/premium/trending/export"),
    ("POST", "https://bottube.ai/api/agents/me/coinbase-wallet"),
    ("GET", "https://rustchain.org/beacon/api/x402/status"),
    ("GET", "https://rustchain.org/beacon/api/premium/reputation"),
    ("GET", "https://rustchain.org/beacon/api/premium/contracts/export"),
    ("GET", "https://rustchain.org/wallet/swap-info"),
    ("POST", "https://rustchain.org/beacon/api/compute/inference"),
    ("GET", "https://rustchain.org/beacon/api/x402/pricing"),
    ("GET", "https://rustchain.org/beacon/api/compute/catalog"),
}


def _endpoint(name):
    return next(item for item in check.ENDPOINTS if item.name == name)


def test_endpoint_matrix_covers_bounty_and_follow_up_routes():
    assert {
        (endpoint.method, endpoint.url) for endpoint in check.ENDPOINTS
    } == EXPECTED_ENDPOINTS


def test_wallet_link_uses_documented_contract_and_redacts_secrets(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok":true}\n__RUSTCHAIN_HTTP_STATUS__:201\n',
        stderr=(
            "> Accept: application/json\n"
            "> X-API-Key: secret-key\n"
            "> Cookie: session=secret-cookie\n"
            "> Content-Type: application/json\n"
            "< HTTP/2 201\n"
            "< Set-Cookie: session=secret-cookie\n"
            "< content-type: application/json\n"
        ),
    )
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return completed

    monkeypatch.setattr(check.subprocess, "run", fake_run)
    wallet_address = "0x1234567890123456789012345678901234567890"

    result = check.run_endpoint(
        _endpoint("bottube_wallet_link"),
        timeout=10,
        api_key="secret-key",
        wallet_address=wallet_address,
    )

    command = captured["command"]
    assert "X-API-Key: secret-key" in command
    assert not any(argument.startswith("Authorization:") for argument in command)
    assert json.loads(command[command.index("--data") + 1]) == {
        "coinbase_address": wallet_address
    }
    assert result.outcome == "PASS"
    assert result.http_status == 201
    assert "< HTTP/2 201" in result.evidence
    assert '{"ok":true}' in result.evidence
    assert "secret-key" not in result.evidence
    assert "secret-cookie" not in result.evidence
    assert "> X-API-Key: [REDACTED]" in result.evidence
    assert "> Cookie: [REDACTED]" in result.evidence
    assert "< Set-Cookie: [REDACTED]" in result.evidence
    assert "Accept: application/json" in result.evidence
    assert "Content-Type: application/json" in result.evidence


def test_unexpected_status_fails_even_when_transport_succeeds(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"ok":true}\n__RUSTCHAIN_HTTP_STATUS__:200\n',
        stderr="< HTTP/2 200\n< content-type: application/json\n",
    )
    monkeypatch.setattr(check.subprocess, "run", lambda *args, **kwargs: completed)

    result = check.run_endpoint(_endpoint("beacon_compute_inference"), timeout=10)

    assert result.outcome == "FAIL"
    assert result.http_status == 200
    assert "expected HTTP 402" in result.reason


def test_invalid_json_fails_a_success_status(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="not-json\n__RUSTCHAIN_HTTP_STATUS__:200\n",
        stderr="< HTTP/2 200\n< content-type: text/html\n",
    )
    monkeypatch.setattr(check.subprocess, "run", lambda *args, **kwargs: completed)

    result = check.run_endpoint(_endpoint("node_swap_info"), timeout=10)

    assert result.outcome == "FAIL"
    assert result.reason == "response body is not valid JSON"


def test_transport_error_cannot_be_reported_as_a_pass(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=6,
        stdout="\n__RUSTCHAIN_HTTP_STATUS__:000\n",
        stderr="Could not resolve host",
    )
    monkeypatch.setattr(check.subprocess, "run", lambda *args, **kwargs: completed)

    result = check.run_endpoint(_endpoint("bottube_x402_status"), timeout=10)

    assert result.outcome == "FAIL"
    assert result.reason == "curl exited with status 6"


def test_wallet_link_is_skipped_without_explicit_credentials():
    result = check.run_endpoint(_endpoint("bottube_wallet_link"), timeout=10)

    assert result.outcome == "SKIP"
    assert "--api-key" in result.reason
    assert "--wallet-address" in result.reason


def test_invalid_wallet_is_rejected_without_sending_request(monkeypatch):
    def unexpected_run(*args, **kwargs):
        raise AssertionError("request should not be sent")

    monkeypatch.setattr(check.subprocess, "run", unexpected_run)

    result = check.run_endpoint(
        _endpoint("bottube_wallet_link"),
        timeout=10,
        api_key="secret-key",
        wallet_address="not-a-base-address",
    )

    assert result.outcome == "FAIL"
    assert result.http_status is None
    assert "40 hexadecimal characters" in result.reason


def test_report_has_one_consistent_summary_row_per_endpoint():
    results = [
        check.CheckResult(
            endpoint=endpoint,
            outcome="PASS",
            http_status=min(endpoint.expected_statuses),
            reason="expected response",
            evidence="evidence",
        )
        for endpoint in check.ENDPOINTS
        if not endpoint.requires_credentials
    ]

    report = check.render_report(results, generated_at="2026-08-28T10:00:00Z")

    assert report.count("| PASS |") == len(results)
    for result in results:
        assert report.count(f"| {result.endpoint.name} |") == 1
    assert "## Raw request/response evidence" in report
