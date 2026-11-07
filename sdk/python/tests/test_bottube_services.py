"""
Tests for BoTTube RTC services client and `rustchain services` CLI.

All HTTP is mocked with respx; unmocked routes raise (respx default).
Money must stay Decimal end to end — never float.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import respx
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rustchain_sdk.bottube import BoTTubeClient, PurchaseReceipt, ServiceOffer
from rustchain_sdk.bottube.client import _api_key_from_config, _money
from rustchain_sdk.bottube.exceptions import (
    APIError,
    ExpiredTokenError,
    InsufficientBalanceError,
    QuantityCapExceededError,
    ServiceError,
    UnknownServiceError,
)
from rustchain_sdk.cli import main

BASE = "https://bottube.ai"

SERVICES_BODY = {
    "services": [
        {
            "key": "video_upload",
            "name": "Video Upload",
            "description": "Upload a video",
            "price_rtc": "0.25",
            "max_quantity": 10,
        },
        {
            "key": "storage_gb",
            "name": "Storage 1 GB",
            # JSON number: parse_float=Decimal keeps this exact.
            "price_rtc": 1.5,
        },
    ]
}

PAY_BODY = {
    "token": "rtc_tok_abc123",
    "service": "video_upload",
    "quantity": 3,
    "unit_price": "0.25",
    "total_cost": "0.75",
    "status": "paid",
}


@pytest.fixture(autouse=True)
def _clean_credential_env(monkeypatch):
    """Keep key resolution deterministic regardless of the developer machine."""
    monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)
    monkeypatch.delenv("BOTTUBE_CONFIG_FILE", raising=False)


@pytest.fixture
def client():
    return BoTTubeClient(api_key="test-key")


def _combined(result):
    """stdout+stderr without duplication across click versions."""
    out = result.output
    stderr = str(getattr(result, "stderr", "") or "")
    return out if stderr in out else out + stderr


class TestMoney:
    def test_rejects_float(self):
        with pytest.raises(TypeError):
            _money(0.1)

    def test_parses_str_int_decimal(self):
        assert _money("0.1234") == Decimal("0.1234")
        assert _money(7) == Decimal(7)
        assert _money(Decimal("2.50")) == Decimal("2.50")

    def test_none_is_zero(self):
        assert _money(None) == Decimal(0)

    def test_rejects_bool(self):
        with pytest.raises(TypeError):
            _money(True)


class TestListServices:
    @respx.mock
    def test_parses_typed_offers_with_decimal_prices(self, client):
        route = respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        offers = client.list_services()
        assert route.called
        assert [o.key for o in offers] == ["video_upload", "storage_gb"]
        first = offers[0]
        assert isinstance(first, ServiceOffer)
        assert first.price == Decimal("0.25")
        assert first.max_quantity == 10
        # JSON number price must be exact Decimal, not float.
        assert isinstance(offers[1].price, Decimal)
        assert offers[1].price == Decimal("1.5")
        assert offers[1].currency == "RTC"

    @respx.mock
    def test_bare_list_response_supported(self, client):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=[{"key": "k", "price": "1"}])
        )
        offers = client.list_services()
        assert len(offers) == 1
        assert offers[0].price == Decimal(1)

    @respx.mock
    def test_sends_bearer_key(self, client):
        route = respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json={"services": []})
        )
        client.list_services()
        assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"


class TestPay:
    @respx.mock
    def test_success_returns_receipt_with_token(self, client):
        route = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json=PAY_BODY)
        )
        receipt = client.pay("video_upload", quantity=3)
        assert isinstance(receipt, PurchaseReceipt)
        assert receipt.token == "rtc_tok_abc123"
        assert receipt.unit_price == Decimal("0.25")
        assert receipt.total_cost == Decimal("0.75")
        body = json.loads(route.calls[0].request.content)
        assert body == {"service": "video_upload", "quantity": 3}

    @respx.mock
    def test_missing_total_computed_in_decimal_exactly(self, client):
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(
                200, json={"token": "t", "service": "s", "unit_price": "0.1234"}
            )
        )
        receipt = client.pay("s", quantity=3)
        assert receipt.total_cost == Decimal("0.3702")  # float math would drift

    @respx.mock
    def test_default_quantity_is_one(self, client):
        route = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json={"token": "t", "unit_price": "1"})
        )
        receipt = client.pay("one")
        assert receipt.quantity == 1
        body = json.loads(route.calls[0].request.content)
        assert body["quantity"] == 1

    @respx.mock
    def test_402_raises_insufficient_balance(self, client):
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(
                402,
                json={"error": {"code": "insufficient_balance",
                                "message": "need 5 RTC, have 1"}},
            )
        )
        with pytest.raises(InsufficientBalanceError) as exc:
            client.pay("video_upload")
        assert exc.value.status_code == 402

    @respx.mock
    def test_404_raises_unknown_service(self, client):
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(
                404, json={"error": {"code": "unknown_service", "message": "nope"}}
            )
        )
        with pytest.raises(UnknownServiceError):
            client.pay("nope")

    @respx.mock
    def test_cap_exceeded(self, client):
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(
                400,
                json={"error": {"code": "quantity_cap",
                                "message": "exceeds max_quantity 10"}},
            )
        )
        with pytest.raises(QuantityCapExceededError):
            client.pay("video_upload", quantity=99)

    @respx.mock
    def test_invalid_quantity_never_hits_network(self, client):
        route = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json={})
        )
        for bad in (0, -1, 2.5, "3", True):
            with pytest.raises(ServiceError):
                client.pay("video_upload", quantity=bad)
        assert route.call_count == 0

    @respx.mock
    def test_empty_service_key_rejected(self, client):
        with pytest.raises(ServiceError):
            client.pay("  ")

    @respx.mock
    def test_server_error_raises_api_error(self, client):
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(500, text="boom")
        )
        with pytest.raises(APIError) as exc:
            client.pay("video_upload")
        assert exc.value.status_code == 500


class TestUse:
    @respx.mock
    def test_success_posts_token_and_payload(self, client):
        route = respx.post(f"{BASE}/api/rtc/use").mock(
            return_value=httpx.Response(200, json={"ok": True, "jobs": 2})
        )
        result = client.use("tok123", url="https://example.com", priority=5)
        assert result["ok"] is True
        body = json.loads(route.calls[0].request.content)
        assert body == {"token": "tok123", "url": "https://example.com",
                        "priority": 5}

    @respx.mock
    def test_expired_token(self, client):
        respx.post(f"{BASE}/api/rtc/use").mock(
            return_value=httpx.Response(
                401, json={"error": {"code": "token_expired",
                                     "message": "token expired"}}
            )
        )
        with pytest.raises(ExpiredTokenError):
            client.use("old-token")

    @respx.mock
    def test_empty_token_rejected(self, client):
        with pytest.raises(ServiceError):
            client.use("")


class TestPurchases:
    @respx.mock
    def test_parses_history_with_decimal_costs(self, client):
        respx.get(f"{BASE}/api/rtc/purchases").mock(
            return_value=httpx.Response(
                200,
                json={"purchases": [PAY_BODY, {
                    "token": "t2", "service": "storage_gb", "quantity": 2,
                    "unit_price": "1.5", "total_cost": "3.0",
                }]},
            )
        )
        receipts = client.purchases()
        assert len(receipts) == 2
        assert receipts[1].total_cost == Decimal("3.0")
        assert all(isinstance(r.total_cost, Decimal) for r in receipts)


class TestApiKeyResolution:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("BOTTUBE_API_KEY", "env-key")
        assert BoTTubeClient().api_key == "env-key"

    def test_from_config_file(self, monkeypatch, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"api_key": "cfg-key"}), encoding="utf-8")
        monkeypatch.setenv("BOTTUBE_CONFIG_FILE", str(cfg))
        assert BoTTubeClient().api_key == "cfg-key"

    def test_missing_everywhere_is_none(self):
        assert BoTTubeClient().api_key is None
        assert _api_key_from_config() is None

    def test_explicit_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("BOTTUBE_API_KEY", "env-key")
        assert BoTTubeClient(api_key="arg-key").api_key == "arg-key"


class TestCLI:
    runner = CliRunner()

    @respx.mock
    def test_list_json(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        result = self.runner.invoke(main, ["services", "list", "--json"])
        assert result.exit_code == 0, _combined(result)
        offers = json.loads(result.output)
        assert offers[0]["key"] == "video_upload"
        # Decimal serialized as string: no float precision loss.
        assert offers[0]["price"] == "0.25"

    @respx.mock
    def test_list_plain_text(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        result = self.runner.invoke(main, ["services", "list"])
        assert result.exit_code == 0, _combined(result)
        assert "video_upload" in result.output
        assert "0.25 RTC" in result.output

    @respx.mock
    def test_buy_yes_prints_price_times_qty_and_pays(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        pay = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json=PAY_BODY)
        )
        result = self.runner.invoke(
            main, ["services", "buy", "video_upload", "--qty", "3", "--yes"]
        )
        assert result.exit_code == 0, _combined(result)
        assert "= 0.75 RTC" in result.output
        assert pay.called

    @respx.mock
    def test_buy_abort_without_yes_skips_pay(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        pay = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json=PAY_BODY)
        )
        result = self.runner.invoke(
            main, ["services", "buy", "video_upload"], input="n\n"
        )
        assert result.exit_code == 0, _combined(result)
        assert "Aborted." in result.output
        assert pay.call_count == 0

    @respx.mock
    def test_buy_confirmed_interactively(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        pay = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json=PAY_BODY)
        )
        result = self.runner.invoke(
            main, ["services", "buy", "video_upload", "--qty", "3"], input="y\n"
        )
        assert result.exit_code == 0, _combined(result)
        assert pay.called

    @respx.mock
    def test_buy_still_pays_when_price_preview_fails(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(500, text="listing down")
        )
        pay = respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(200, json=PAY_BODY)
        )
        result = self.runner.invoke(
            main, ["services", "buy", "video_upload", "--yes"]
        )
        assert result.exit_code == 0, _combined(result)
        assert pay.called

    @respx.mock
    def test_buy_402_exits_nonzero(self):
        respx.get(f"{BASE}/api/rtc/services").mock(
            return_value=httpx.Response(200, json=SERVICES_BODY)
        )
        respx.post(f"{BASE}/api/rtc/pay").mock(
            return_value=httpx.Response(
                402, json={"error": {"message": "insufficient RTC balance"}}
            )
        )
        result = self.runner.invoke(
            main, ["services", "buy", "video_upload", "--yes"]
        )
        assert result.exit_code == 1
        assert "insufficient" in _combined(result).lower()

    def test_buy_rejects_qty_zero(self):
        result = self.runner.invoke(
            main, ["services", "buy", "x", "--qty", "0", "--yes"]
        )
        assert result.exit_code == 1
        assert "must be >= 1" in _combined(result)

    @respx.mock
    def test_use_posts_payload(self):
        route = respx.post(f"{BASE}/api/rtc/use").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = self.runner.invoke(
            main, ["services", "use", "tok123", "url=https://x.io", "--json"]
        )
        assert result.exit_code == 0, _combined(result)
        body = json.loads(route.calls[0].request.content)
        assert body["token"] == "tok123"
        assert body["url"] == "https://x.io"
        assert json.loads(result.output)["ok"] is True

    @respx.mock
    def test_use_expired_token_exits_nonzero(self):
        respx.post(f"{BASE}/api/rtc/use").mock(
            return_value=httpx.Response(
                401, json={"error": {"code": "token_expired"}}
            )
        )
        result = self.runner.invoke(main, ["services", "use", "old"])
        assert result.exit_code == 1
        assert "expired" in _combined(result).lower()

    @respx.mock
    def test_purchases_json(self):
        respx.get(f"{BASE}/api/rtc/purchases").mock(
            return_value=httpx.Response(200, json={"purchases": [PAY_BODY]})
        )
        result = self.runner.invoke(main, ["services", "purchases", "--json"])
        assert result.exit_code == 0, _combined(result)
        rows = json.loads(result.output)
        assert rows[0]["total_cost"] == "0.75"

    @respx.mock
    def test_purchases_plain_text(self):
        respx.get(f"{BASE}/api/rtc/purchases").mock(
            return_value=httpx.Response(200, json={"purchases": [PAY_BODY]})
        )
        result = self.runner.invoke(main, ["services", "purchases"])
        assert result.exit_code == 0, _combined(result)
        assert "video_upload" in result.output

    def test_no_api_key_flag_anywhere(self):
        """Secret is env/config only: no CLI flag could leak it to history."""
        for args in (["services", "list"], ["services", "buy", "x"],
                     ["services", "use", "t"], ["services", "purchases"]):
            result = self.runner.invoke(main, args + ["--help"])
            assert "--api-key" not in result.output
