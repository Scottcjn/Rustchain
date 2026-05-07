from flask import Flask, request, jsonify
from validator.validate_genesis import validate_genesis
import tempfile
import os
import json

app = Flask(__name__)

@app.route('/validate', methods=['POST'])
def validate():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Save the file temporarily
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        result = validate_genesis(tmp_path)
        return jsonify(result)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
