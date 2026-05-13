# SPDX-License-Identifier: MIT

import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request
from validator.validate_genesis import validate_genesis

app = Flask(__name__)
MAX_FILE_SIZE = int(os.environ.get("POA_API_MAX_FILE_SIZE", 10 * 1024 * 1024))
MAX_UPLOAD_CHUNK_SIZE = 64 * 1024
JSON_MIME_TYPES = {"", "application/json", "application/octet-stream", "text/json"}


def is_json_upload(file):
    return Path(file.filename or "").suffix.lower() == ".json" and (file.mimetype or "") in JSON_MIME_TYPES


def save_limited_upload(file, destination):
    total_size = 0
    with open(destination, "wb") as output:
        while True:
            chunk = file.stream.read(MAX_UPLOAD_CHUNK_SIZE)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                raise ValueError("File too large")

            output.write(chunk)


@app.route('/validate', methods=['POST'])
def validate():
    if request.content_length is not None and request.content_length > MAX_FILE_SIZE:
        return jsonify({"error": "File too large"}), 413

    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not is_json_upload(file):
        return jsonify({"error": "Only JSON files accepted"}), 400

    tmp_path = None
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
        tmp_path = tmp.name

    try:
        save_limited_upload(file, tmp_path)
        result = validate_genesis(tmp_path)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 413
    except Exception:
        app.logger.exception("PoA genesis validation failed")
        return jsonify({"error": "Validation failed"}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
