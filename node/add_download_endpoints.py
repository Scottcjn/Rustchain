#!/usr/bin/env python3
"""
Add download endpoints to existing RustChain server
"""
import sys

# Read the existing server file
with open('/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py', 'r') as f:
    content = f.read()

# Check if download endpoints already exist
if '@app.route("/download/installer")' in content:
    print("Download endpoints already exist!")
    sys.exit(0)

# Find where to insert the new endpoints (before if __name__)
insert_point = content.find('if __name__ == "__main__":')

if insert_point == -1:
    print("Could not find insertion point")
    sys.exit(1)

# New endpoints code
new_endpoints = '''
# Windows Miner Download Endpoints
from flask import send_file

@app.route("/download/installer")
def download_installer():
    """Download Windows installer batch file"""
    try:
        return send_file(
            "/root/rustchain/install_rustchain_windows.bat",
            as_attachment=True,
            download_name="install_rustchain_windows.bat",
            mimetype="application/x-bat"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/download/miner")
def download_miner():
    """Download Windows miner Python file"""
    try:
        return send_file(
            "/root/rustchain/rustchain_windows_miner.py",
            as_attachment=True,
            download_name="rustchain_windows_miner.py",
            mimetype="text/x-python"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/downloads")
def downloads_page():
    """Simple downloads page"""
    html = """
    <html>
    <head><title>RustChain Downloads</title></head>
    <body style='font-family: monospace; background: #0a0a0a; color: #00ff00; padding: 40px;'>
        <h1>🦀 RustChain Windows Miner</h1>
        <h2>📥 Downloads</h2>
        <p><a href='/download/installer' style='color: #00ff00;'>⚡ Download Installer (.bat)</a></p>
        <p><a href='/download/miner' style='color: #00ff00;'>🐍 Download Miner (.py)</a></p>
        <h3>Installation:</h3>
        <ol>
            <li>Download the installer</li>
            <li>Right-click and 'Run as Administrator'</li>
            <li>Follow the prompts</li>
        </ol>
        <p>Network: <code>50.28.86.131:8088</code></p>
    </body>
    </html>
    """
    return html

'''

# Insert the new endpoints
new_content = content[:insert_point] + new_endpoints + content[insert_point:]

# Write back
with open('/root/rustchain/rustchain_v2_integrated_v2.2.1_rip200.py', 'w') as f:
    f.write(new_content)

print("✅ Download endpoints added successfully!")
