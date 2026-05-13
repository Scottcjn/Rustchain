# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify
from validator.validate_genesis import validate_genesis
import tempfile
import os

app = Flask(__name__)

MAX_UPLOAD_BYTES = int(os.environ.get("POA_VALIDATE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
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

    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"File too large (max {MAX_UPLOAD_BYTES} bytes)"}), 413

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
