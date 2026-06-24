import importlib.util
import ssl
from pathlib import Path


def load_dashboard_module():
    module_path = Path(__file__).with_name("dashboard.py")
    spec = importlib.util.spec_from_file_location("tui_dashboard", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ssl_context_verifies_tls_by_default():
    dashboard = load_dashboard_module()

    ctx = dashboard._ssl_ctx()

    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_ssl_context_allows_explicit_insecure_tls():
    dashboard = load_dashboard_module()

    ctx = dashboard._ssl_ctx(insecure_tls=True)

    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False
