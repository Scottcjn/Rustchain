import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "sdk" / "rustchain" / "exceptions.py"


def load_exceptions_module():
    spec = importlib.util.spec_from_file_location("sdk_rustchain_exceptions", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sdk_exception_classes_share_rustchain_base():
    exc = load_exceptions_module()

    for cls in [
        exc.ConnectionError,
        exc.ValidationError,
        exc.APIError,
        exc.AttestationError,
        exc.TransferError,
    ]:
        assert issubclass(cls, exc.RustChainError)
        assert issubclass(cls, Exception)


def test_simple_sdk_exceptions_preserve_message_text():
    exc = load_exceptions_module()

    assert str(exc.ConnectionError("node unavailable")) == "node unavailable"
    assert str(exc.ValidationError("bad wallet")) == "bad wallet"
    assert str(exc.AttestationError("bad proof")) == "bad proof"
    assert str(exc.TransferError("insufficient funds")) == "insufficient funds"


def test_api_error_keeps_status_code_and_response_payload():
    exc = load_exceptions_module()

    err = exc.APIError(
        "request failed",
        status_code=429,
        response={"error": "rate_limited"},
    )

    assert str(err) == "request failed"
    assert err.status_code == 429
    assert err.response == {"error": "rate_limited"}


def test_api_error_defaults_optional_metadata_to_none():
    exc = load_exceptions_module()

    err = exc.APIError("request failed")

    assert err.status_code is None
    assert err.response is None
