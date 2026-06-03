import importlib.util
import io
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "rustchain_download_page.py"


def load_download_page_module():
    spec = importlib.util.spec_from_file_location("rustchain_download_page_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_handler(module, path):
    handler = module.DownloadHandler.__new__(module.DownloadHandler)
    handler.path = path
    handler.wfile = io.BytesIO()
    handler.responses = []
    handler.headers = []
    handler.errors = []

    handler.send_response = lambda code: handler.responses.append(code)
    handler.send_header = lambda name, value: handler.headers.append((name, value))
    handler.end_headers = lambda: None
    handler.send_error = lambda code, message=None: handler.errors.append((code, message))
    return handler


def test_index_route_serves_download_html():
    module = load_download_page_module()
    handler = make_handler(module, "/")

    handler.do_GET()

    assert handler.responses == [200]
    assert ("Content-type", "text/html") in handler.headers
    body = handler.wfile.getvalue().decode()
    assert "RustChain Miner Downloads" in body
    assert "rustchain_miners_v2.2.1.zip" in body


def test_index_html_route_serves_same_download_html():
    module = load_download_page_module()
    handler = make_handler(module, "/index.html")

    handler.do_GET()

    assert handler.responses == [200]
    assert "RustChain Miner Downloads" in handler.wfile.getvalue().decode()


def test_download_route_rejects_path_traversal(tmp_path):
    module = load_download_page_module()
    module.DOWNLOAD_DIR = str(tmp_path)
    handler = make_handler(module, "/../secret.txt")

    handler.do_GET()

    assert handler.errors == [(403, "Forbidden")]
    assert handler.responses == []
    assert handler.wfile.getvalue() == b""


def test_download_route_serves_python_file_with_attachment_headers(tmp_path):
    module = load_download_page_module()
    module.DOWNLOAD_DIR = str(tmp_path)
    miner = tmp_path / "rustchain_linux_miner.py"
    miner.write_text("print('mine')\n")
    handler = make_handler(module, f"/{miner.name}")

    handler.do_GET()

    assert handler.responses == [200]
    assert ("Content-type", "text/plain") in handler.headers
    assert ("Content-Disposition", f'attachment; filename="{miner.name}"') in handler.headers
    assert handler.wfile.getvalue() == b"print('mine')\n"


def test_download_route_returns_404_for_missing_file(tmp_path):
    module = load_download_page_module()
    module.DOWNLOAD_DIR = str(tmp_path)
    handler = make_handler(module, "/missing.zip")

    handler.do_GET()

    assert handler.errors == [(404, "File not found: missing.zip")]
    assert handler.responses == []
