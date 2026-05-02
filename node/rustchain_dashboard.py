#!/usr/bin/env python3
import os

from flask import Flask

app = Flask(__name__)

DB_PATH = os.environ.get("RUSTCHAIN_DB_PATH", "rustchain_v2.db")


@app.route("/")
def dashboard():
    return "Dashboard content here"


if __name__ == "__main__":
    # For SSL: use nginx reverse proxy or flask-tls
    app.run(host="0.0.0.0", port=8099, debug=False)  # nosec B104
