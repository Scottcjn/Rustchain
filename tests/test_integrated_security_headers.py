import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = PROJECT_ROOT / "node" / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_integrated_node():
    module_name = "integrated_node_security_headers_test"
    if module_name in sys.modules:
        return sys.modules[module_name]

    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "node"))
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    os.environ.setdefault("DB_PATH", ":memory:")

    spec = importlib.util.spec_from_file_location(module_name, NODE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_health_response_includes_security_headers():
    integrated_node = _load_integrated_node()
    client = integrated_node.app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
