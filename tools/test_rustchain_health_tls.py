import importlib.util
import ssl
from pathlib import Path


def load_health_module():
    module_path = Path(__file__).with_name("rustchain-health.py")
    spec = importlib.util.spec_from_file_location("rustchain_health", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_health_cli_verifies_tls_by_default():
    health = load_health_module()

    ctx = health._ssl_ctx()

    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_health_cli_insecure_tls_is_explicit():
    health = load_health_module()

    ctx = health._ssl_ctx(insecure_tls=True)

    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False
