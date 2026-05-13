# SPDX-License-Identifier: MIT

import importlib.util
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
POA_ROOT = REPO_ROOT / "rustchain-poa"
POA_API_PATH = POA_ROOT / "api" / "poa_api.py"

sys.path.insert(0, str(POA_ROOT))
spec = importlib.util.spec_from_file_location("poa_api", POA_API_PATH)
poa_api = importlib.util.module_from_spec(spec)
sys.modules["poa_api"] = poa_api
spec.loader.exec_module(poa_api)


def post_upload(client, body=b"{}", filename="genesis.json"):
    return client.post(
        "/validate",
        data={"file": (io.BytesIO(body), filename)},
        content_type="multipart/form-data",
    )


def test_validate_rejects_missing_file():
    poa_api.app.config["TESTING"] = True
    client = poa_api.app.test_client()

    response = client.post("/validate", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert response.get_json()["error"] == "No file part in request"


def test_validate_rejects_non_json_filename():
    poa_api.app.config["TESTING"] = True
    client = poa_api.app.test_client()

    response = post_upload(client, body=b"{}", filename="genesis.txt")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Only JSON files accepted"


def test_validate_rejects_large_upload():
    poa_api.app.config["TESTING"] = True
    client = poa_api.app.test_client()

    with patch.object(poa_api, "MAX_FILE_SIZE", 8):
        response = post_upload(client, body=b"123456789", filename="genesis.json")

    assert response.status_code == 413
    assert response.get_json()["error"] == "File too large"


def test_validate_deletes_temp_file_after_success():
    poa_api.app.config["TESTING"] = True
    client = poa_api.app.test_client()
    seen_path = {}

    def fake_validate(path):
        seen_path["path"] = path
        assert os.path.exists(path)
        return {"validated": True}

    with patch.object(poa_api, "validate_genesis", side_effect=fake_validate):
        response = post_upload(client)

    assert response.status_code == 200
    assert response.get_json() == {"validated": True}
    assert seen_path["path"]
    assert not os.path.exists(seen_path["path"])


def test_validate_returns_generic_error_and_deletes_temp_file():
    poa_api.app.config["TESTING"] = True
    client = poa_api.app.test_client()
    seen_path = {}

    def failing_validate(path):
        seen_path["path"] = path
        assert os.path.exists(path)
        raise RuntimeError("/tmp/private-validator-detail")

    with patch.object(poa_api, "validate_genesis", side_effect=failing_validate):
        response = post_upload(client)

    assert response.status_code == 500
    assert response.get_json()["error"] == "Validation failed"
    assert b"private-validator-detail" not in response.data
    assert seen_path["path"]
    assert not os.path.exists(seen_path["path"])
