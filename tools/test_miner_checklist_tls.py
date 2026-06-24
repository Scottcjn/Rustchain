import importlib.util
import ssl
from pathlib import Path


def load_checklist_module():
    module_path = Path(__file__).with_name("miner_checklist.py")
    spec = importlib.util.spec_from_file_location("miner_checklist", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_miner_checklist_verifies_tls_by_default():
    checklist = load_checklist_module()

    ctx = checklist._ssl_context()

    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_miner_checklist_insecure_tls_is_explicit():
    checklist = load_checklist_module()

    ctx = checklist._ssl_context(insecure_tls=True)

    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False
