"""
Unit tests for BoTTube RTC Services SDK (`list_services`, `pay`, `use`, `purchases`)
and CLI (`rustchain services list|buy|use|purchases`) — Bounty #17183.

Verifies:
- All 4 `/api/rtc/*` endpoints wrapped with typed dataclasses (`RTCService`,
  `RTCPaymentReceipt`, `RTCServiceUseResult`, `RTCPurchaseRecord`).
- Strict `Decimal` money math (zero `float` values for RTC amounts).
- Explicit typed exceptions (`InsufficientRTCBalanceError` on HTTP 402,
  `ExpiredServiceTokenError`, `UnknownServiceError`, `QuantityCapExceededError`).
- CLI `rustchain services list|buy|use|purchases` including `price × qty` confirmation,
  `--yes`, and `--json` output, with API key loaded from env/config (never CLI flags).
"""

from decimal import Decimal
import io
import json
from urllib.error import HTTPError
from unittest.mock import patch

from click.testing import CliRunner
import pytest

from rustchain_sdk.bottube import (
    BoTTubeClient,
    ExpiredServiceTokenError,
    InsufficientRTCBalanceError,
    QuantityCapExceededError,
    RTCPaymentReceipt,
    RTCPurchaseRecord,
    RTCService,
    RTCServiceUseResult,
    UnknownServiceError,
)
from rustchain_sdk.cli import main as cli_main


SAMPLE_SERVICES_PAYLOAD = {
    "note": "Pay with RTC. Need RTC? Top up at /credits",
    "services": [
        {
            "service_key": "inference_single",
            "name": "POWER8 Deep Chat",
            "description": "One chat request to GPT-OSS 120B on IBM POWER8 S824 (512GB RAM)",
            "price_rtc": 3.0,
            "ttl_hours": 0.1,
            "uses": 1,
        },
        {
            "service_key": "pro_api_day",
            "name": "Pro API Day Pass",
            "description": "24-hour access to premium analytics, trending export, and reputation endpoints",
            "price_rtc": 10.0,
            "ttl_hours": 24.0,
            "uses": 1000,
        },
    ],
}


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _make_http_error(url: str, code: int, body_dict: dict) -> HTTPError:
    fp = io.BytesIO(json.dumps(body_dict).encode("utf-8"))
    return HTTPError(url=url, code=code, msg="HTTP Error", hdrs=None, fp=fp)


def test_list_services_returns_typed_decimal_models():
    client = BoTTubeClient(api_key="test_env_key")
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(SAMPLE_SERVICES_PAYLOAD)):
        services = client.list_services()
    assert len(services) == 2
    assert isinstance(services[0], RTCService)
    assert services[0].service_key == "inference_single"
    assert isinstance(services[0].price_rtc, Decimal)
    assert services[0].price_rtc == Decimal("3.0")
    assert isinstance(services[0].ttl_hours, Decimal)
    assert services[0].ttl_hours == Decimal("0.1")
    assert services[0].uses == 1


def test_pay_use_and_purchases_happy_path_decimal_only():
    client = BoTTubeClient(api_key="test_env_key")
    pay_resp = {
        "purchase_id": "pur_17183_power8",
        "service_key": "inference_single",
        "service_token": "tok_power8_s824_xyz",
        "quantity": 1,
        "amount_rtc": "3.0",
        "uses_remaining": 1,
        "expires_at": "1794191381.212458",
        "balance_remaining_rtc": "17.0",
    }
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(pay_resp)):
        receipt = client.pay("inference_single", quantity=1)
    assert isinstance(receipt, RTCPaymentReceipt)
    assert receipt.service_token == "tok_power8_s824_xyz"
    assert isinstance(receipt.amount_rtc, Decimal)
    assert receipt.amount_rtc == Decimal("3.0")
    assert receipt.balance_remaining_rtc == Decimal("17.0")
    assert receipt.purchase_id == "pur_17183_power8"

    use_resp = {
        "ok": True,
        "service_key": "inference_single",
        "uses_remaining": 0,
        "result": {"model": "gpt-oss-120b-power8", "response": "Proof-of-Antiquity rewards real vintage silicon."},
    }
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(use_resp)):
        used = client.use(receipt.service_token, prompt="Explain PoA")
    assert isinstance(used, RTCServiceUseResult)
    assert used.ok is True
    assert used.uses_remaining == 0
    assert used.result["model"] == "gpt-oss-120b-power8"

    purchases_resp = {
        "purchases": [
            {
                "purchase_id": "pur_17183_power8",
                "service_key": "inference_single",
                "quantity": 1,
                "amount_rtc": "3.0",
                "status": "exhausted",
                "uses_total": 1,
                "uses_remaining": 0,
                "created_at": "1794191081.212458",
                "expires_at": "1794191381.212458",
                "token_hash": "c28d0dc6c4d665e81f4e816b63557a83c3fd3c963875b95b3d83dc9d60df637f",
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(purchases_resp)):
        records = client.purchases()
    assert len(records) == 1
    assert isinstance(records[0], RTCPurchaseRecord)
    assert isinstance(records[0].amount_rtc, Decimal)
    assert records[0].amount_rtc == Decimal("3.0")
    assert records[0].status == "exhausted"


def test_explicit_exceptions_for_402_expired_unknown_and_quantity_cap():
    client = BoTTubeClient(api_key="test_env_key")

    # 1. HTTP 402 Insufficient RTC Balance
    err_402 = _make_http_error(
        "https://bottube.ai/api/rtc/pay",
        402,
        {"error": "Insufficient RTC balance", "required_rtc": "3.0", "available_rtc": "1.5"},
    )
    with patch("urllib.request.urlopen", side_effect=err_402):
        with pytest.raises(InsufficientRTCBalanceError) as exc_info:
            client.pay("inference_single", quantity=1)
        assert exc_info.value.status_code == 402
        assert exc_info.value.required_rtc == Decimal("3.0")
        assert exc_info.value.available_rtc == Decimal("1.5")

    # 2. Expired / Exhausted service token on /api/rtc/use
    err_410 = _make_http_error(
        "https://bottube.ai/api/rtc/use",
        410,
        {"error": "Service token expired or has 0 remaining uses"},
    )
    with patch("urllib.request.urlopen", side_effect=err_410):
        with pytest.raises(ExpiredServiceTokenError):
            client.use("tok_expired_123", prompt="test")

    # 3. Unknown service key on /api/rtc/pay
    err_404 = _make_http_error(
        "https://bottube.ai/api/rtc/pay",
        404,
        {"error": "Unknown service_key: nonexistent_svc"},
    )
    with patch("urllib.request.urlopen", side_effect=err_404):
        with pytest.raises(UnknownServiceError) as exc_unknown:
            client.pay("nonexistent_svc", quantity=1)
        assert exc_unknown.value.service_key == "nonexistent_svc"

    # 4. Quantity over server cap (client-side & server-side)
    with pytest.raises(QuantityCapExceededError):
        client.pay("inference_single", quantity=0)
    with pytest.raises(QuantityCapExceededError):
        client.pay("inference_single", quantity=101)


def test_cli_services_list_buy_use_and_purchases(monkeypatch):
    monkeypatch.setenv("BOTTUBE_API_KEY", "env_secret_bottube_key")
    runner = CliRunner()

    # 1. rustchain services list --json
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(SAMPLE_SERVICES_PAYLOAD)):
        res_list = runner.invoke(cli_main, ["services", "list", "--json"])
        assert res_list.exit_code == 0
        parsed = json.loads(res_list.output)
        assert parsed[0]["service_key"] == "inference_single"
        assert parsed[0]["price_rtc"] == "3.0"

    # 2. rustchain services buy inference_single --qty 2 (interactive confirmation prompt shows 3.0 RTC × 2 = 6.0 RTC)
    pay_resp = {
        "purchase_id": "pur_cli_2",
        "service_key": "inference_single",
        "service_token": "tok_cli_xyz",
        "quantity": 2,
        "amount_rtc": "6.0",
        "uses_remaining": 2,
    }
    with patch(
        "urllib.request.urlopen",
        side_effect=[_FakeHTTPResponse(SAMPLE_SERVICES_PAYLOAD), _FakeHTTPResponse(pay_resp)],
    ):
        res_buy = runner.invoke(cli_main, ["services", "buy", "inference_single", "--qty", "2"], input="y\n")
        assert res_buy.exit_code == 0
        assert "3.0 RTC × 2 = 6.0 RTC" in res_buy.output
        assert "tok_cli_xyz" in res_buy.output

    # 3. rustchain services buy inference_single --qty 1 --yes --json
    with patch(
        "urllib.request.urlopen",
        side_effect=[_FakeHTTPResponse(SAMPLE_SERVICES_PAYLOAD), _FakeHTTPResponse(pay_resp)],
    ):
        res_buy_json = runner.invoke(cli_main, ["services", "buy", "inference_single", "--qty", "2", "--yes", "--json"])
        assert res_buy_json.exit_code == 0
        assert json.loads(res_buy_json.output)["service_token"] == "tok_cli_xyz"

    # 4. rustchain services use <token> --prompt "Hello" --json
    use_resp = {"ok": True, "service_key": "inference_single", "uses_remaining": 1, "result": {"reply": "Hi from POWER8"}}
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(use_resp)):
        res_use = runner.invoke(cli_main, ["services", "use", "tok_cli_xyz", "--prompt", "Hello", "--json"])
        assert res_use.exit_code == 0
        assert json.loads(res_use.output)["result"]["reply"] == "Hi from POWER8"

    # 5. rustchain services purchases --json
    purchases_resp = {
        "purchases": [
            {
                "purchase_id": "pur_cli_2",
                "service_key": "inference_single",
                "quantity": 2,
                "amount_rtc": "6.0",
                "status": "active",
                "uses_total": 2,
                "uses_remaining": 1,
            }
        ]
    }
    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(purchases_resp)):
        res_pur = runner.invoke(cli_main, ["services", "purchases", "--json"])
        assert res_pur.exit_code == 0
        assert json.loads(res_pur.output)[0]["amount_rtc"] == "6.0"
