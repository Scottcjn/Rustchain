import importlib.util
import ssl
from pathlib import Path


def load_miner_score_module():
    module_path = Path(__file__).with_name("miner_score.py")
    spec = importlib.util.spec_from_file_location("miner_score", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_miner_score_verifies_tls_by_default():
    miner_score = load_miner_score_module()

    ctx = miner_score._ssl_context()

    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_miner_score_insecure_tls_is_explicit():
    miner_score = load_miner_score_module()

    ctx = miner_score._ssl_context(insecure_tls=True)

    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False
