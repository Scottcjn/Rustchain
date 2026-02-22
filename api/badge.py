import hashlib
import time
from flask import Flask, send_file, request
import io

app = Flask(__name__)

def generate_svg(status="Active"):
    color = "#4c1" if status == "Active" else "#9f9f9f"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="100" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <path fill="#555" d="M0 0h60v20H0z"/>
    <path fill="{color}" d="M60 0h40v20H60z"/>
    <path fill="url(#b)" d="M0 0h100v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="30" y="15" fill="#010101" fill-opacity=".3">Mining</text>
    <text x="30" y="14">Mining</text>
    <text x="80" y="15" fill="#010101" fill-opacity=".3">{status}</text>
    <text x="80" y="14">{status}</text>
  </g>
</svg>"""
    return svg

@app.route("/api/badge")
def mining_badge():
    # Simple logic: if a heartbeat happened in the last 15 mins, it's active
    # For a real implementation, this would query the node's memory or DB
    status = "Active"
    svg = generate_svg(status)
    return svg, 200, {"Content-Type": "image/svg+xml"}

if __name__ == "__main__":
    app.run(port=8082)
