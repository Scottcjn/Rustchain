"""
Unit tests for rustchain_sdk.exceptions

Tests all exception classes, inheritance hierarchy,
message/detail handling, repr output, and edge cases.
"""

import pytest

from rustchain_sdk.exceptions import (
    RustChainError,
    ConnectionError,
    APIError,
    AuthenticationError,
    ValidationError,
    WalletError,
    AttestationError,
    GovernanceError,
    HealthError,
    EpochError,
    TransferError,
    RPCError,
)


class TestRustChainError:
    """Base exception tests."""

    def test_message_only(self):
        err = RustChainError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.details == {}

    def test_message_with_details(self):
        details = {"code": 42, "reason": "test"}
        err = RustChainError("something went wrong", details=details)
        assert err.message == "something went wrong"
        assert err.details == {"code": 42, "reason": "test"}

    def test_details_default_is_dict_not_none(self):
        err = RustChainError("msg")
        assert isinstance(err.details, dict)
        # Mutating default should not affect other instances
        err.details["key"] = "val"
        err2 = RustChainError("msg2")
        assert err2.details == {}

    def test_repr_format(self):
        err = RustChainError("test error")
        assert repr(err) == "RustChainError('test error')"

    def test_repr_with_special_chars(self):
        err = RustChainError("it's a \"test\"")
        assert "RustChainError" in repr(err)
        assert "test" in repr(err)

    def test_inheritance_chain(self):
        assert issubclass(ConnectionError, RustChainError)
        assert issubclass(APIError, RustChainError)
        assert issubclass(RPCError, RustChainError)
        assert issubclass(RustChainError, Exception)

    def test_catch_base_catches_all(self):
        for cls in [ConnectionError, APIError, AuthenticationError,
                     ValidationError, WalletError, AttestationError,
                     GovernanceError, HealthError, EpochError,
                     TransferError, RPCError]:
            with pytest.raises(RustChainError):
                raise cls("test")

    def test_empty_message(self):
        err = RustChainError("")
        assert str(err) == ""
        assert err.message == ""


class TestConnectionError:
    """Connection-specific error tests."""

    def test_basic(self):
        err = ConnectionError("node unreachable")
        assert err.message == "node unreachable"
        assert err.details == {}

    def test_with_details(self):
        err = ConnectionError("timeout", details={"host": "50.28.86.131", "timeout": 30})
        assert err.details["host"] == "50.28.86.131"
        assert err.details["timeout"] == 30

    def test_inheritance(self):
        err = ConnectionError("test")
        assert isinstance(err, RustChainError)


class TestAPIError:
    """API error with status code tests."""

    def test_basic(self):
        err = APIError("bad request")
        assert err.message == "bad request"
        assert err.status_code is None
        assert err.response_body == {}

    def test_with_status_code(self):
        err = APIError("not found", status_code=404)
        assert err.status_code == 404

    def test_with_response_body(self):
        body = {"error": "wallet not found"}
        err = APIError("not found", status_code=404, response_body=body)
        assert err.response_body == {"error": "wallet not found"}

    def test_repr_includes_status(self):
        err = APIError("server error", status_code=500)
        r = repr(err)
        assert "500" in r
        assert "APIError" in r

    def test_repr_without_status(self):
        err = APIError("unknown error")
        r = repr(err)
        assert "APIError" in r
        assert "None" in r  # status_code is None

    def test_edge_case_zero_status(self):
        err = APIError("network error", status_code=0)
        assert err.status_code == 0


class TestRPCError:
    """RPC error with method tracking tests."""

    def test_basic(self):
        err = RPCError("health", "node down")
        assert err.message == "node down"
        assert err.method == "health"
        assert err.details == {}

    def test_with_details(self):
        err = RPCError("transfer", "insufficient funds", details={"balance": 0})
        assert err.details["balance"] == 0

    def test_empty_method(self):
        err = RPCError("", "no method specified")
        assert err.method == ""

    def test_long_method_name(self):
        method = "a" * 1000
        err = RPCError(method, "test")
        assert err.method == method


class TestSimpleExceptions:
    """Test all simple pass-through exceptions."""

    @pytest.mark.parametrize("cls", [
        AuthenticationError,
        ValidationError,
        WalletError,
        AttestationError,
        GovernanceError,
        HealthError,
        EpochError,
        TransferError,
    ])
    def test_basic_creation(self, cls):
        err = cls("test message")
        assert str(err) == "test message"
        assert isinstance(err, RustChainError)
        assert err.details == {}

    @pytest.mark.parametrize("cls", [
        AuthenticationError,
        ValidationError,
        WalletError,
        AttestationError,
        GovernanceError,
        HealthError,
        EpochError,
        TransferError,
    ])
    def test_with_details(self, cls):
        err = cls("test", details={"key": "val"})
        assert err.details == {"key": "val"}
