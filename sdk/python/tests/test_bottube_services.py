# SPDX-License-Identifier: MIT
"""Unit tests for ``rustchain_sdk.bottube`` RTC services and ``rustchain services`` CLI (#17183).

All HTTP calls are mocked in-process so no test ever contacts a live server.
Covers:
- ``list_services()``, ``pay()``, ``use()``, ``purchases()``
- Strict ``Decimal`` RTC amounts (no ``float`` on money)
- Explicit typed exceptions: ``InsufficientRTCBalanceError`` (402),
  ``ExpiredServiceTokenError`` (410/404), ``UnknownServiceError`` (400/404),
  ``QuantityCapExceededError`` (cap > 100 or < 1)
- CLI: ``rustchain services list|buy|use|purchases`` with ``--qty``, ``--yes``,
  interactive confirmation prompt, and ``--json``
- Credential hygiene: API key read from env/config only, never via CLI flag or logged
"""

from __future__ import annotations

import inspect
import io
import json
import sys
import urllib.error
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from rustchain_sdk.bottube import (
    MAX_PURCHASE_QUANTITY,
    AuthenticationError,
    BoTTubeClient,
    ExpiredServiceTokenError,
    InsufficientRTCBalanceError,
    QuantityCapExceededError,
    RTCPayReceipt,
    RTCPurchaseHistory,
    RTCPurchaseItem,
    RTCServiceOffer,
    RTCUseReceipt,
    UnknownServiceError,
    resolve_api_key,
    to_rtc_decimal,
)
from rustchain_sdk.cli import main, services_group


class _MockHTTPResponse:
    def __init__(self, payload: Any, status: int = 200):
        self.status = status
        self._raw = (
            payload.encode("utf-8")
            if isinstance(payload, str)
            else json.dumps(payload).encode("utf-8")
        )

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_MockHTTPResponse":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _http_error(url: str, code: int, body_obj: Any, reason: str = "Error") -> urllib.error.HTTPError:
    raw = (
        body_obj.encode("utf-8")
        if isinstance(body_obj, str)
        else json.dumps(body_obj).encode("utf-8")
    )
    return urllib.error.HTTPError(url, code, reason, {}, io.BytesIO(raw))


@pytest.fixture
def runner() -> CliRunner:
    params = inspect.signature(CliRunner.__init__).parameters
    if "mix_stderr" in params:
        return CliRunner(mix_stderr=False)
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("BOTTUBE_API_KEY", "bt_test_secret_key_do_not_log")
    monkeypatch.setenv("BOTTUBE_CONFIG_FILE", str(tmp_path / "nonexistent.json"))


SAMPLE_SERVICES_RESPONSE = {
    "services": [
        {
            "service_key": "pro_api_day",
            "name": "Pro API Day Pass",
            "description": "24-hour access to premium endpoints",
            "price_rtc": 10.0,
            "ttl_hours": 24.0,
            "uses": 1000,
        },
        {
            "service_key": "inference_single",
            "name": "POWER8 Deep Chat",
            "description": "One chat request to GPT-OSS 120B on IBM POWER8 S824",
            "price_rtc": 3.0,
            "ttl_hours": 0.1,
            "uses": 1,
        },
    ],
    "note": "Pay with RTC. Need RTC? Top up at /credits",
}


# ---------------------------------------------------------------------------
# 1. Decimal money math & credential resolution
# ---------------------------------------------------------------------------


def test_to_rtc_decimal_accepts_decimal_int_str_and_rejects_float_and_bool():
    assert to_rtc_decimal(Decimal("3.0")) == Decimal("3.0")
    assert to_rtc_decimal(3) == Decimal("3")
    assert to_rtc_decimal("0.123456") == Decimal("0.123456")
    with pytest.raises(TypeError, match="never float"):
        to_rtc_decimal(3.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="never float/bool"):
        to_rtc_decimal(True)  # type: ignore[arg-type]


def test_api_key_resolution_env_and_config_and_never_in_repr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    secret = "bt_super_secret_999"
    monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)
    cfg = tmp_path / "bottube_cfg.json"
    cfg.write_text(json.dumps({"api_key": secret}), encoding="utf-8")
    monkeypatch.setenv("BOTTUBE_CONFIG_FILE", str(cfg))

    assert resolve_api_key() == secret
    client = BoTTubeClient()
    assert client.api_key == secret
    assert secret not in repr(client)


def test_no_api_key_flag_on_any_services_cli_command():
    """Ensure API key can never be passed via a CLI flag that lands in shell history."""
    all_param_names = set()
    for p in services_group.params:
        all_param_names.update(p.opts)
    for sub_cmd in services_group.commands.values():
        for p in sub_cmd.params:
            all_param_names.update(p.opts)
            all_param_names.add(p.name or "")
    forbidden = {"--api-key", "--key", "--token-key", "api_key"}
    assert all_param_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# 2. Client methods: list_services(), pay(), use(), purchases()
# ---------------------------------------------------------------------------


def test_client_list_services_returns_typed_offers_with_decimal():
    captured_reqs = []

    def fake_urlopen(req, context=None, timeout=30):
        captured_reqs.append(req)
        return _MockHTTPResponse(SAMPLE_SERVICES_RESPONSE)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client = BoTTubeClient()
        offers = client.list_services()

    assert len(offers) == 2
    assert isinstance(offers[0], RTCServiceOffer)
    assert offers[1].service_key == "inference_single"
    assert offers[1].name == "POWER8 Deep Chat"
    assert isinstance(offers[1].price_rtc, Decimal)
    assert offers[1].price_rtc == Decimal("3.0")
    assert isinstance(offers[1].ttl_hours, Decimal)
    assert offers[1].ttl_hours == Decimal("0.1")
    assert offers[1].uses == 1
    assert captured_reqs[0].headers.get("X-api-key") == "bt_test_secret_key_do_not_log"


def test_client_pay_success_returns_typed_receipt_with_decimal():
    pay_response = {
        "ok": True,
        "service": "POWER8 Deep Chat",
        "service_key": "inference_single",
        "amount_rtc": 3.0,
        "service_token": "rtc_svc_tok_abcdef123456",
        "expires_at": 1794045000.5,
        "expires_in_hours": 0.1,
        "uses_remaining": 1,
        "balance_remaining": 12.25,
        "note": "Store this token",
    }
    sent_bodies = []

    def fake_urlopen(req, context=None, timeout=30):
        sent_bodies.append(json.loads(req.data.decode("utf-8")))
        return _MockHTTPResponse(pay_response)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        receipt = BoTTubeClient().pay("inference_single", quantity=1)

    assert isinstance(receipt, RTCPayReceipt)
    assert receipt.ok is True
    assert receipt.service_key == "inference_single"
    assert receipt.service_token == "rtc_svc_tok_abcdef123456"
    assert isinstance(receipt.amount_rtc, Decimal)
    assert receipt.amount_rtc == Decimal("3.0")
    assert isinstance(receipt.balance_remaining, Decimal)
    assert receipt.balance_remaining == Decimal("12.25")
    assert sent_bodies == [{"service_key": "inference_single", "quantity": 1}]


def test_client_pay_402_raises_insufficient_balance_with_decimals():
    err_payload = {
        "error": "Insufficient RTC balance",
        "balance": 0.5,
        "cost": 3.0,
        "need": 2.5,
    }
    with patch(
        "urllib.request.urlopen",
        side_effect=_http_error("https://bottube.ai/api/rtc/pay", 402, err_payload),
    ):
        with pytest.raises(InsufficientRTCBalanceError) as exc_info:
            BoTTubeClient().pay("inference_single", quantity=1)

    err = exc_info.value
    assert err.status_code == 402
    assert err.balance == Decimal("0.5")
    assert err.cost == Decimal("3.0")
    assert err.need == Decimal("2.5")


@pytest.mark.parametrize("status_code", [400, 404])
def test_client_pay_unknown_service_raises_unknown_service_error(status_code: int):
    err_payload = {
        "error": "Unknown service: bogus_svc",
        "available": ["pro_api_day", "inference_single"],
    }
    with patch(
        "urllib.request.urlopen",
        side_effect=_http_error("https://bottube.ai/api/rtc/pay", status_code, err_payload),
    ):
        with pytest.raises(UnknownServiceError) as exc_info:
            BoTTubeClient().pay("bogus_svc")

    assert "pro_api_day" in exc_info.value.available


@pytest.mark.parametrize("bad_qty", [0, -2, MAX_PURCHASE_QUANTITY + 1, 999])
def test_client_pay_quantity_over_cap_or_non_positive_raises_locally(bad_qty: int):
    with patch("urllib.request.urlopen") as mock_open:
        with pytest.raises(QuantityCapExceededError):
            BoTTubeClient().pay("inference_single", quantity=bad_qty)
    assert not mock_open.called


def test_client_use_success_and_expired_token_error():
    use_response = {
        "ok": True,
        "service_key": "inference_single",
        "uses_remaining": 0,
        "expires_at": 1794045000.0,
        "output": "POWER8 response",
    }
    captured_body = []

    def fake_urlopen(req, context=None, timeout=30):
        captured_body.append(json.loads(req.data.decode("utf-8")))
        return _MockHTTPResponse(use_response)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        receipt = BoTTubeClient().use("rtc_svc_tok_123", prompt="Hello POWER8")

    assert isinstance(receipt, RTCUseReceipt)
    assert receipt.ok is True
    assert receipt.service_key == "inference_single"
    assert receipt.uses_remaining == 0
    assert receipt.data["output"] == "POWER8 response"
    assert captured_body == [{"service_token": "rtc_svc_tok_123", "prompt": "Hello POWER8"}]

    # Expired token (410) and invalid/expired token (404) both raise ExpiredServiceTokenError
    for code, msg in ((410, "Token expired"), (404, "Invalid or expired token")):
        with patch(
            "urllib.request.urlopen",
            side_effect=_http_error("https://bottube.ai/api/rtc/use", code, {"error": msg}),
        ):
            with pytest.raises(ExpiredServiceTokenError):
                BoTTubeClient().use("rtc_svc_tok_expired")


def test_client_purchases_returns_typed_history_with_decimal():
    purchases_payload = {
        "balance": 9.5,
        "purchases": [
            {
                "id": 42,
                "service_key": "inference_single",
                "quantity": 1,
                "amount_rtc": 3.0,
                "status": "exhausted",
                "uses_total": 1,
                "uses_remaining": 0,
                "created_at": 1794042000.0,
                "expires_at": 1794042300.0,
            }
        ],
    }
    with patch(
        "urllib.request.urlopen",
        return_value=_MockHTTPResponse(purchases_payload),
    ):
        hist = BoTTubeClient().purchases()

    assert isinstance(hist, RTCPurchaseHistory)
    assert isinstance(hist.balance, Decimal)
    assert hist.balance == Decimal("9.5")
    assert len(hist.purchases) == 1
    item = hist.purchases[0]
    assert isinstance(item, RTCPurchaseItem)
    assert item.service_key == "inference_single"
    assert isinstance(item.amount_rtc, Decimal)
    assert item.amount_rtc == Decimal("3.0")
    assert item.purchase_id == "42"


# ---------------------------------------------------------------------------
# 3. CLI commands: rustchain services list | buy | use | purchases
# ---------------------------------------------------------------------------


def test_cli_services_list_human_and_json(runner: CliRunner):
    with patch(
        "urllib.request.urlopen",
        return_value=_MockHTTPResponse(SAMPLE_SERVICES_RESPONSE),
    ):
        human = runner.invoke(main, ["services", "list"])
    assert human.exit_code == 0, human.stderr
    assert "inference_single" in human.stdout
    assert "3.0 RTC" in human.stdout
    assert "POWER8 Deep Chat" in human.stdout

    with patch(
        "urllib.request.urlopen",
        return_value=_MockHTTPResponse(SAMPLE_SERVICES_RESPONSE),
    ):
        as_json = runner.invoke(main, ["services", "list", "--json"])
    assert as_json.exit_code == 0, as_json.stderr
    parsed = json.loads(as_json.stdout)
    assert len(parsed["services"]) == 2
    assert parsed["services"][1]["service_key"] == "inference_single"
    assert parsed["services"][1]["price_rtc"] == "3.0"


def test_cli_services_buy_prints_price_times_qty_and_handles_confirm_and_yes(
    runner: CliRunner,
):
    pay_resp = {
        "ok": True,
        "service": "POWER8 Deep Chat",
        "service_key": "inference_single",
        "amount_rtc": 6.0,
        "service_token": "rtc_svc_tok_buy2",
        "uses_remaining": 2,
        "balance_remaining": 4.0,
    }

    def router(req, context=None, timeout=30):
        if req.full_url.endswith("/api/rtc/services"):
            return _MockHTTPResponse(SAMPLE_SERVICES_RESPONSE)
        return _MockHTTPResponse(pay_resp)

    # 1. Without --yes, declining confirmation aborts and never calls /api/rtc/pay
    calls = []

    def abort_router(req, context=None, timeout=30):
        calls.append(req.full_url)
        return router(req, context, timeout)

    with patch("urllib.request.urlopen", side_effect=abort_router):
        aborted = runner.invoke(
            main, ["services", "buy", "inference_single", "--qty", "2"], input="n\n"
        )
    assert aborted.exit_code == 1
    assert "3.0 RTC × 2 = 6.0 RTC" in aborted.stdout
    assert not any(u.endswith("/api/rtc/pay") for u in calls)

    # 2. With --yes, prints price × qty and completes purchase
    with patch("urllib.request.urlopen", side_effect=router):
        bought = runner.invoke(
            main, ["services", "buy", "inference_single", "--qty", "2", "--yes"]
        )
    assert bought.exit_code == 0, bought.stderr
    assert "3.0 RTC × 2 = 6.0 RTC" in bought.stdout
    assert "rtc_svc_tok_buy2" in bought.stdout

    # 3. With --yes --json, outputs valid JSON receipt
    with patch("urllib.request.urlopen", side_effect=router):
        bought_json = runner.invoke(
            main,
            ["services", "buy", "inference_single", "--qty", "2", "--yes", "--json"],
        )
    assert bought_json.exit_code == 0, bought_json.stderr
    parsed = json.loads(bought_json.stdout)
    assert parsed["service_token"] == "rtc_svc_tok_buy2"
    assert parsed["amount_rtc"] == "6.0"


def test_cli_services_buy_402_exits_nonzero(runner: CliRunner):
    def router(req, context=None, timeout=30):
        if req.full_url.endswith("/api/rtc/services"):
            return _MockHTTPResponse(SAMPLE_SERVICES_RESPONSE)
        raise _http_error(
            req.full_url,
            402,
            {"error": "Insufficient RTC balance", "balance": 0.0, "cost": 3.0, "need": 3.0},
        )

    with patch("urllib.request.urlopen", side_effect=router):
        res = runner.invoke(main, ["services", "buy", "inference_single", "--yes"])
    assert res.exit_code == 1
    assert "Insufficient RTC balance" in res.stderr


def test_cli_services_use_and_purchases_human_and_json(runner: CliRunner):
    use_resp = {
        "ok": True,
        "service_key": "inference_single",
        "uses_remaining": 0,
        "expires_at": 1794045000.0,
    }
    with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(use_resp)):
        used = runner.invoke(
            main,
            ["services", "use", "rtc_svc_tok_xyz", "prompt=hello", "--json"],
        )
    assert used.exit_code == 0, used.stderr
    assert json.loads(used.stdout)["service_key"] == "inference_single"

    purchases_resp = {
        "balance": 0.0,
        "purchases": [
            {
                "service_key": "inference_single",
                "quantity": 1,
                "amount_rtc": 3.0,
                "status": "exhausted",
                "uses_total": 1,
                "uses_remaining": 0,
                "created_at": 1794042500.0,
                "expires_at": 1794042800.0,
            }
        ],
    }
    with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(purchases_resp)):
        purch_human = runner.invoke(main, ["services", "purchases"])
    assert purch_human.exit_code == 0, purch_human.stderr
    assert "inference_single" in purch_human.stdout
    assert "3.0 RTC" in purch_human.stdout

    with patch("urllib.request.urlopen", return_value=_MockHTTPResponse(purchases_resp)):
        purch_json = runner.invoke(main, ["services", "purchases", "--json"])
    assert purch_json.exit_code == 0, purch_json.stderr
    parsed_p = json.loads(purch_json.stdout)
    assert parsed_p["balance"] == "0.0"
    assert parsed_p["purchases"][0]["service_key"] == "inference_single"
