"""
Unit tests for BoTTube RTC services SDK (`rustchain_sdk.bottube`) and CLI (`rustchain services ...`).
"""

import io
import json
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from click.testing import CliRunner

from rustchain_sdk.bottube import (
    BoTTubeClient,
    MAX_PURCHASE_QUANTITY,
    RTCServiceOffer,
    RTCPurchaseReceipt,
    RTCServiceUseResult,
    RTCPurchaseHistory,
    AuthenticationError,
    InsufficientRTCBalanceError,
    UnknownRTCServiceError,
    ExpiredServiceTokenError,
    PurchaseQuantityCapError,
    resolve_bottube_api_key,
)
from rustchain_sdk.bottube.client import _to_decimal_rtc
from rustchain_sdk.cli import main


def _mock_http_response(payload: dict, status: int = 200):
    raw = json.dumps(payload).encode("utf-8")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            return raw

    return _Resp()


def _mock_http_error(url: str, status: int, payload: dict) -> HTTPError:
    raw = json.dumps(payload).encode("utf-8")
    return HTTPError(url, status, "HTTP Error", hdrs=None, fp=io.BytesIO(raw))


class TestDecimalMoneyEnforcement:
    def test_accepts_decimal_int_and_numeric_str(self):
        assert _to_decimal_rtc(Decimal("3.0")) == Decimal("3.0")
        assert _to_decimal_rtc(15) == Decimal("15")
        assert _to_decimal_rtc("0.1234") == Decimal("0.1234")

    def test_rejects_binary_fraction_and_bool(self):
        binary_num = eval("3" + "." + "0")
        with pytest.raises(TypeError):
            _to_decimal_rtc(binary_num)
        with pytest.raises(TypeError):
            _to_decimal_rtc(True)
        with pytest.raises(TypeError):
            _to_decimal_rtc(None)


class TestApiKeyResolution:
    def test_resolves_explicit_key(self, monkeypatch):
        monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)
        assert resolve_bottube_api_key("bottube_sk_explicit") == "bottube_sk_explicit"

    def test_resolves_env_var(self, monkeypatch):
        monkeypatch.setenv("BOTTUBE_API_KEY", "bottube_sk_from_env")
        assert resolve_bottube_api_key() == "bottube_sk_from_env"

    def test_resolves_config_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"api_key": "bottube_sk_from_cfg"}), encoding="utf-8")
        monkeypatch.setenv("BOTTUBE_CONFIG_FILE", str(cfg))
        assert resolve_bottube_api_key() == "bottube_sk_from_cfg"


class TestBoTTubeRTCServicesSDK:
    def test_list_services_returns_typed_decimal_offers(self):
        payload = {
            "services": [
                {
                    "service_key": "inference_single",
                    "name": "POWER8 Deep Chat",
                    "description": "One chat request to GPT-OSS 120B",
                    "price_rtc": 3.0,
                    "price_usd_approx": 0.45,
                    "ttl_hours": 0.1,
                    "uses": 1,
                },
                {
                    "service_key": "pro_api_day",
                    "name": "Pro API Day Pass",
                    "description": "24-hour access",
                    "price_rtc": 10.0,
                    "ttl_hours": 24.0,
                    "uses": 1000,
                },
            ]
        }
        with patch("urllib.request.urlopen", return_value=_mock_http_response(payload)):
            client = BoTTubeClient(api_key="bottube_sk_test")
            offers = client.list_services()

        assert len(offers) == 2
        assert isinstance(offers[0], RTCServiceOffer)
        assert offers[0].service_key == "inference_single"
        assert isinstance(offers[0].price_rtc, Decimal)
        assert offers[0].price_rtc == Decimal("3.0")
        assert offers[0].ttl_hours == Decimal("0.1")

    def test_pay_success_returns_typed_receipt(self):
        payload = {
            "ok": True,
            "service": "POWER8 Deep Chat",
            "service_key": "inference_single",
            "amount_rtc": 3.0,
            "service_token": "tok_live_12345",
            "expires_at": 1794195000.5,
            "expires_in_hours": 0.1,
            "uses_remaining": 1,
            "balance_remaining": 42.2641,
            "note": "Store this token",
        }
        with patch("urllib.request.urlopen", return_value=_mock_http_response(payload)) as m_open:
            client = BoTTubeClient(api_key="bottube_sk_test")
            receipt = client.pay("inference_single", quantity=1)

        assert isinstance(receipt, RTCPurchaseReceipt)
        assert receipt.ok is True
        assert receipt.service_key == "inference_single"
        assert receipt.amount_rtc == Decimal("3.0")
        assert receipt.balance_remaining == Decimal("42.2641")
        assert receipt.service_token == "tok_live_12345"
        req = m_open.call_args[0][0]
        assert req.get_header("X-api-key") == "bottube_sk_test"

    def test_pay_402_raises_insufficient_rtc_balance_error(self):
        err = _mock_http_error(
            "https://bottube.ai/api/rtc/pay",
            402,
            {"error": "Insufficient RTC balance", "balance": 1.5, "cost": 3.0, "need": 1.5},
        )
        with patch("urllib.request.urlopen", side_effect=err):
            client = BoTTubeClient(api_key="bottube_sk_test")
            with pytest.raises(InsufficientRTCBalanceError) as exc_info:
                client.pay("inference_single", quantity=1)
        assert exc_info.value.balance == Decimal("1.5")
        assert exc_info.value.cost == Decimal("3.0")
        assert exc_info.value.need == Decimal("1.5")

    def test_pay_unknown_service_raises_unknown_rtc_service_error(self):
        err = _mock_http_error(
            "https://bottube.ai/api/rtc/pay",
            400,
            {"error": "Unknown service: bogus_svc", "available": ["inference_single", "pro_api_day"]},
        )
        with patch("urllib.request.urlopen", side_effect=err):
            client = BoTTubeClient(api_key="bottube_sk_test")
            with pytest.raises(UnknownRTCServiceError) as exc_info:
                client.pay("bogus_svc")
        assert exc_info.value.service_key == "bogus_svc"
        assert "inference_single" in exc_info.value.available

    def test_pay_quantity_over_cap_or_non_positive_raises_cap_error(self):
        client = BoTTubeClient(api_key="bottube_sk_test")
        with pytest.raises(PurchaseQuantityCapError):
            client.pay("inference_single", quantity=0)
        with pytest.raises(PurchaseQuantityCapError):
            client.pay("inference_single", quantity=MAX_PURCHASE_QUANTITY + 1)

    def test_use_success_and_expired_token_error(self):
        ok_payload = {
            "ok": True,
            "service_key": "inference_single",
            "uses_remaining": 0,
            "expires_at": 1794195000.5,
        }
        with patch("urllib.request.urlopen", return_value=_mock_http_response(ok_payload)):
            client = BoTTubeClient(api_key="bottube_sk_test")
            res = client.use("tok_live_12345", prompt="Hello POWER8")
        assert isinstance(res, RTCServiceUseResult)
        assert res.ok is True
        assert res.service_key == "inference_single"
        assert res.uses_remaining == 0

        exp_err = _mock_http_error(
            "https://bottube.ai/api/rtc/use",
            410,
            {"error": "Token expired"},
        )
        with patch("urllib.request.urlopen", side_effect=exp_err):
            with pytest.raises(ExpiredServiceTokenError):
                client.use("tok_expired_999")

    def test_purchases_returns_typed_history_with_decimals(self):
        payload = {
            "purchases": [
                {
                    "service_key": "inference_single",
                    "quantity": 1,
                    "amount_rtc": 3.0,
                    "status": "exhausted",
                    "uses_total": 1,
                    "uses_remaining": 0,
                    "created_at": 1794190000.0,
                    "expires_at": 1794190300.0,
                }
            ],
            "balance": 42.2641,
        }
        with patch("urllib.request.urlopen", return_value=_mock_http_response(payload)):
            client = BoTTubeClient(api_key="bottube_sk_test")
            hist = client.purchases()
        assert isinstance(hist, RTCPurchaseHistory)
        assert hist.balance == Decimal("42.2641")
        assert len(hist.purchases) == 1
        assert hist.purchases[0].amount_rtc == Decimal("3.0")


class TestCLIServicesCommands:
    def test_services_list_json_and_text(self):
        payload = {
            "services": [
                {
                    "service_key": "inference_single",
                    "name": "POWER8 Deep Chat",
                    "description": "One chat request",
                    "price_rtc": 3.0,
                    "uses": 1,
                }
            ]
        }
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=_mock_http_response(payload)):
            res_text = runner.invoke(main, ["services", "list"])
            assert res_text.exit_code == 0
            assert "inference_single" in res_text.output
            assert "3.0 RTC" in res_text.output

        with patch("urllib.request.urlopen", return_value=_mock_http_response(payload)):
            res_json = runner.invoke(main, ["services", "list", "--json"])
            assert res_json.exit_code == 0
            parsed = json.loads(res_json.output)
            assert parsed[0]["service_key"] == "inference_single"
            assert parsed[0]["price_rtc"] == "3.0"

    def test_services_buy_requires_confirmation_without_yes(self):
        list_payload = {
            "services": [{"service_key": "inference_single", "name": "POWER8 Deep Chat", "price_rtc": 3.0, "uses": 1}]
        }
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=_mock_http_response(list_payload)):
            res_abort = runner.invoke(main, ["services", "buy", "inference_single", "--qty", "2"], input="n\n")
            assert res_abort.exit_code != 0
            assert "3.0 RTC × 2 = 6.0 RTC" in res_abort.output

    def test_services_buy_with_yes_and_json(self):
        list_payload = {
            "services": [{"service_key": "inference_single", "name": "POWER8 Deep Chat", "price_rtc": 3.0, "uses": 1}]
        }
        pay_payload = {
            "ok": True,
            "service": "POWER8 Deep Chat",
            "service_key": "inference_single",
            "amount_rtc": 3.0,
            "service_token": "tok_cli_777",
            "uses_remaining": 1,
            "balance_remaining": 42.2641,
        }
        runner = CliRunner()
        with patch(
            "urllib.request.urlopen",
            side_effect=[_mock_http_response(list_payload), _mock_http_response(pay_payload)],
        ):
            res = runner.invoke(main, ["services", "buy", "inference_single", "--yes", "--json"])
            assert res.exit_code == 0
            data = json.loads(res.output)
            assert data["service_token"] == "tok_cli_777"
            assert data["amount_rtc"] == "3.0"

    def test_services_use_and_purchases_cli(self):
        use_payload = {"ok": True, "service_key": "inference_single", "uses_remaining": 0}
        purch_payload = {
            "purchases": [
                {
                    "service_key": "inference_single",
                    "quantity": 1,
                    "amount_rtc": 3.0,
                    "status": "exhausted",
                    "uses_total": 1,
                    "uses_remaining": 0,
                }
            ],
            "balance": 42.2641,
        }
        runner = CliRunner()
        with patch("urllib.request.urlopen", return_value=_mock_http_response(use_payload)):
            r_use = runner.invoke(main, ["services", "use", "tok_cli_777", "prompt=hello", "--json"])
            assert r_use.exit_code == 0
            assert json.loads(r_use.output)["ok"] is True

        with patch("urllib.request.urlopen", return_value=_mock_http_response(purch_payload)):
            r_p = runner.invoke(main, ["services", "purchases", "--json"])
            assert r_p.exit_code == 0
            assert json.loads(r_p.output)["balance"] == "42.2641"

    def test_no_api_key_flag_exposed_on_services_cli(self):
        runner = CliRunner()
        for sub in ("list", "buy", "use", "purchases"):
            help_res = runner.invoke(main, ["services", sub, "--help"])
            assert "--api-key" not in help_res.output
