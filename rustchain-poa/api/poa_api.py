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
    
    # Security: Validate file size (max 5MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        return jsonify({"error": "File too large (max 5MB)"}), 413
    
    # Security: Validate file extension
    if not file.filename.lower().endswith('.json'):
        return jsonify({"error": "Invalid file type (only .json allowed)"}), 400

    # Save the file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = validate_genesis(tmp_path)
        os.remove(tmp_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
