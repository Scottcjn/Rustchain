# SPDX-License-Identifier: MIT

import os
import tempfile

from flask import Flask, jsonify, request
from validator.validate_genesis import validate_genesis
from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)

MAX_UPLOAD_BYTES = int(os.environ.get("POA_VALIDATE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_MULTIPART_OVERHEAD_BYTES = int(
    os.environ.get("POA_VALIDATE_MULTIPART_OVERHEAD_BYTES", str(128 * 1024))
)
UPLOAD_CHUNK_BYTES = 64 * 1024
JSON_MIME_TYPES = {"", "application/json", "text/json"}


def _max_request_bytes() -> int:
    return MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD_BYTES


app.config["MAX_CONTENT_LENGTH"] = _max_request_bytes()


def _file_too_large_response():
    return jsonify({"error": f"File too large (max {MAX_UPLOAD_BYTES} bytes)"}), 413


@app.errorhandler(RequestEntityTooLarge)
def _handle_request_too_large(_exc):
    return _file_too_large_response()


def _is_json_upload(file) -> bool:
    filename = (file.filename or "").lower()
    mimetype = (file.mimetype or "").split(";", 1)[0].lower()
    return filename.endswith(".json") and mimetype in JSON_MIME_TYPES


def _copy_limited_upload(src, dst) -> bool:
    """Copy upload data to dst, returning False when the upload exceeds the cap."""
    total = 0
    while True:
        chunk = src.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            return False
        dst.write(chunk)
    return True


@app.route('/validate', methods=['POST'])
def validate():
    if request.content_length is not None and request.content_length > _max_request_bytes():
        return _file_too_large_response()

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
                return _file_too_large_response()

        result = validate_genesis(tmp_path)
        return jsonify(result)
    except Exception:
        app.logger.exception("PoA genesis validation failed")
        return jsonify({"error": "Validation failed"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
