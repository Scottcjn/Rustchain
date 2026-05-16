# SPDX-License-Identifier: MIT
import importlib.util
import io
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POA_API_PATH = REPO_ROOT / "rustchain-poa" / "api" / "poa_api.py"


def load_poa_api(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO_ROOT / "rustchain-poa"))
    module_name = "poa_api_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, POA_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


def test_validate_rejects_non_json_upload(monkeypatch):
    module = load_poa_api(monkeypatch)
    called = False

    def fake_validate(_path):
        nonlocal called
        called = True
        return {"ok": True}

    module.validate_genesis = fake_validate

    response = module.app.test_client().post(
        "/validate",
        data={"file": (io.BytesIO(b"{}"), "proof.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Only JSON files accepted"}
    assert called is False


def test_validate_rejects_oversized_upload_before_validation(monkeypatch):
    module = load_poa_api(monkeypatch)
    module.MAX_UPLOAD_BYTES = 64
    called = False

    def fake_validate(_path):
        nonlocal called
        called = True
        return {"ok": True}

    module.validate_genesis = fake_validate

    response = module.app.test_client().post(
        "/validate",
        data={"file": (io.BytesIO(b"{" + b'"x":' + b'"' + (b"a" * 128) + b'"}'), "proof.json")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert "File too large" in response.get_json()["error"]
    assert called is False


def test_validate_uses_generic_error_and_cleans_temp_file(monkeypatch):
    module = load_poa_api(monkeypatch)
    seen_path = {}

    def fake_validate(path):
        temp_path = Path(path)
        assert temp_path.exists()
        seen_path["path"] = temp_path
        raise RuntimeError("internal path C:/secret/schema.db leaked")

    module.validate_genesis = fake_validate

    response = module.app.test_client().post(
        "/validate",
        data={"file": (io.BytesIO(b"{}"), "proof.json")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Validation failed"}
    assert "secret" not in response.get_data(as_text=True)
    assert seen_path["path"].exists() is False


def test_validate_accepts_valid_json_upload_and_cleans_temp_file(monkeypatch):
    module = load_poa_api(monkeypatch)
    seen_path = {}

    def fake_validate(path):
        temp_path = Path(path)
        assert temp_path.exists()
        seen_path["path"] = temp_path
        assert temp_path.read_text(encoding="utf-8") == '{"ok": true}'
        return {"valid": True}

    module.validate_genesis = fake_validate

    response = module.app.test_client().post(
        "/validate",
        data={"file": (io.BytesIO(b'{"ok": true}'), "proof.json")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json() == {"valid": True}
    assert seen_path["path"].exists() is False
