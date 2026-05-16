import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "rustchain_download_server.py"


def load_download_server_module():
    spec = importlib.util.spec_from_file_location("rustchain_download_server_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    return module


def test_index_route_renders_download_page():
    module = load_download_server_module()

    response = module.app.test_client().get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "RustChain Miner Downloads" in body
    assert "/downloads/rustchain_miners_v2.2.1.zip" in body
    assert "Block Reward" in body


def test_download_route_serves_existing_file_as_attachment(tmp_path):
    module = load_download_server_module()
    module.DOWNLOAD_DIR = str(tmp_path)
    miner = tmp_path / "rustchain_linux_miner.py"
    miner.write_text("print('mine')\n")

    response = module.app.test_client().get(f"/downloads/{miner.name}")

    assert response.status_code == 200
    assert response.get_data() == b"print('mine')\n"
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert f"filename={miner.name}" in response.headers["Content-Disposition"]


def test_download_route_returns_404_for_missing_file(tmp_path):
    module = load_download_server_module()
    module.DOWNLOAD_DIR = str(tmp_path)

    response = module.app.test_client().get("/downloads/missing.zip")

    assert response.status_code == 404


def test_download_route_does_not_serve_parent_directory_paths(tmp_path):
    module = load_download_server_module()
    module.DOWNLOAD_DIR = str(tmp_path / "downloads")
    Path(module.DOWNLOAD_DIR).mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve")

    response = module.app.test_client().get("/downloads/../secret.txt")

    assert response.status_code == 404
    assert b"do not serve" not in response.get_data()
