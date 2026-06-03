import importlib.util
import io
import ssl
import urllib.error
from pathlib import Path
from types import SimpleNamespace


def load_server():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "epoch-viz"
        / "server.py"
    )
    spec = importlib.util.spec_from_file_location("epoch_viz_server", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_handler(module):
    handler = object.__new__(module.ProxyHandler)
    handler.responses = []
    handler.headers = []
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: handler.responses.append(code)
    handler.send_header = lambda key, value: handler.headers.append((key, value))
    handler.end_headers = lambda: handler.headers.append(("__end__", ""))
    return handler


class FakeUrlResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def test_do_get_proxies_api_and_epoch_paths():
    module = load_server()
    handler = make_handler(module)
    proxied_paths = []
    handler.proxy_request = lambda path: proxied_paths.append(path)

    handler.path = "/api/status"
    handler.do_GET()
    handler.path = "/epoch"
    handler.do_GET()

    assert proxied_paths == ["/api/status", "/epoch"]


def test_proxy_request_writes_json_response(monkeypatch):
    module = load_server()
    handler = make_handler(module)
    contexts = []
    opened = []

    def fake_context():
        context = SimpleNamespace(check_hostname=True, verify_mode="CERT_REQUIRED")
        contexts.append(context)
        return context

    def fake_urlopen(request, timeout, context):
        opened.append((request.full_url, timeout, context))
        return FakeUrlResponse(b'{"ok":true}')

    monkeypatch.setattr(ssl, "create_default_context", fake_context)
    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    handler.proxy_request("/epoch")

    assert handler.responses == [200]
    assert ("Content-Type", "application/json") in handler.headers
    assert ("Access-Control-Allow-Origin", "*") in handler.headers
    assert handler.wfile.getvalue() == b'{"ok":true}'
    assert opened == [(f"{module.NODE_URL}/epoch", 15, contexts[0])]


def test_proxy_request_reports_url_errors(monkeypatch):
    module = load_server()
    handler = make_handler(module)
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda request, timeout, context: (_ for _ in ()).throw(
            urllib.error.URLError("offline")
        ),
    )

    handler.proxy_request("/epoch")

    assert handler.responses == [500]
    assert ("Content-Type", "application/json") in handler.headers
    assert b"offline" in handler.wfile.getvalue()
