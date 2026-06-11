# SPDX-License-Identifier: MIT

import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request

POA_ROOT = Path(__file__).resolve().parents[1]
if str(POA_ROOT) not in sys.path:
    sys.path.insert(0, str(POA_ROOT))

from validator.validate_genesis import validate_genesis

app = Flask(__name__)


def _env_positive_int(name, default):
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return value


MAX_UPLOAD_BYTES = _env_positive_int("POA_VALIDATE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
JSON_MIME_TYPES = {"", "application/json", "text/json"}


def _is_json_upload(file) -> bool:
    filename = (file.filename or "").lower()
    mimetype = (file.mimetype or "").split(";", 1)[0].lower()
    return filename.endswith(".json") and mimetype in JSON_MIME_TYPES


def _copy_limited_upload(src, dst) -> bool:
    """Copy upload data to dst, returning False when the upload exceeds the cap."""
    total = 0
    while True:
        chunk = src.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            return False
        dst.write(chunk)
    return True


@app.route('/validate', methods=['POST'])
def validate():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not _is_json_upload(file):
        return jsonify({"error": "Only JSON files accepted"}), 400

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            tmp_path = tmp.name
            if hasattr(file.stream, "seek"):
                file.stream.seek(0)
            if not _copy_limited_upload(file.stream, tmp):
                return jsonify({"error": f"File too large (max {MAX_UPLOAD_BYTES} bytes)"}), 413

        result = validate_genesis(tmp_path)
        return jsonify(result)
    except Exception:
        return jsonify({"error": "Validation failed"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
