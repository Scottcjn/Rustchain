#!/usr/bin/env python3
"""
RustChain Miner Download Server
Serves miners via HTTP on port 8090
"""

from flask import Flask, send_from_directory, render_template_string
import os

app = Flask(__name__)
DOWNLOAD_DIR = "/root/rustchain/downloads"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RustChain Miner Downloads</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            max-width: 900px;
            margin: 50px auto;
            padding: 20px;
            background: #0a0a0a;
            color: #00ff00;
        }
        h1 {
            color: #00ff00;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
        }
        h2 {
            color: #00ff00;
            margin-top: 30px;
        }
        .download-section {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .download-link {
            display: block;
            background: #003300;
            color: #00ff00;
            padding: 15px;
            margin: 10px 0;
            text-decoration: none;
            border: 1px solid #00ff00;
            border-radius: 3px;
            font-size: 16px;
            transition: all 0.3s;
        }
        .download-link:hover {
            background: #00ff00;
            color: #000;
        }
        .file-size {
            float: right;
            color: #888;
        }
        .platform-badge {
            display: inline-block;
            background: #00ff00;
            color: #000;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 10px;
        }
        .stats {
            background: #1a1a1a;
            border: 1px solid #00ff00;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .stats p {
            margin: 5px 0;
        }
        code {
            background: #000;
            color: #00ff00;
            padding: 2px 6px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <h1>🦀 RustChain Miner Downloads</h1>
    
    <div class="stats">
        <p><strong>Node</strong>: rustchain.org</p>
        <p><strong>Version</strong>: 2.2.1</p>
        <p><strong>Block Time</strong>: 600 seconds (10 min)</p>
        <p><strong>Block Reward</strong>: 1.5 RTC</p>
    </div>

    <h2>📦 Complete Package (All Platforms)</h2>
    <div class="download-section">
        <a href="/downloads/rustchain_miners_v2.2.1.zip" class="download-link">
            <span class="platform-badge">ALL</span>
            rustchain_miners_v2.2.1.zip
            <span class="file-size">18 KB</span>
        </a>
        <p>Includes: PowerPC G4, Mac (Intel/M1), Linux, Windows + README</p>
    </div>

    <h2>💻 Individual Miners</h2>
    
    <div class="download-section">
        <h3>PowerPC G4/G5 Mac (2.5x Mining Power!)</h3>
        <a href="/downloads/rustchain_powerpc_g4_miner.py" class="download-link">
            <span class="platform-badge">PPC</span>
            rustchain_powerpc_g4_miner.py
            <span class="file-size">7.1 KB</span>
        </a>
        <p><strong>Supported</strong>: Power Mac G4/G5, PowerBook G4, iMac G4/G5</p>
        <p><strong>OS</strong>: Mac OS X 10.2 - 10.5</p>
        <p><strong>Power</strong>: 2.5x base (Classic Tier)</p>
        <p><strong>Run</strong>: <code>python rustchain_powerpc_g4_miner.py</code></p>
    </div>

    <div class="download-section">
        <h3>Mac (Intel & Apple Silicon)</h3>
        <a href="/downloads/rustchain_mac_universal_miner.py" class="download-link">
            <span class="platform-badge">MAC</span>
            rustchain_mac_universal_miner.py
            <span class="file-size">25 KB</span>
        </a>
        <p><strong>Supported</strong>: Intel Mac (2010+), Apple Silicon (M1/M2/M3)</p>
        <p><strong>OS</strong>: macOS 10.15+</p>
        <p><strong>Power</strong>: 1.0x base (Modern Tier)</p>
        <p><strong>Run</strong>: <code>python3 rustchain_mac_universal_miner.py</code></p>
    </div>

    <div class="download-section">
        <h3>Linux (x86_64, ARM, RISC-V)</h3>
        <a href="/downloads/rustchain_linux_miner.py" class="download-link">
            <span class="platform-badge">LINUX</span>
            rustchain_linux_miner.py
            <span class="file-size">7.7 KB</span>
        </a>
        <p><strong>Supported</strong>: Ubuntu, Debian, Fedora, Arch, Raspberry Pi</p>
        <p><strong>Power</strong>: 1.0x base (Modern Tier)</p>
        <p><strong>Run</strong>: <code>python3 rustchain_linux_miner.py</code></p>
    </div>

    <div class="download-section">
        <h3>Windows (x86_64)</h3>
        <a href="/downloads/rustchain_windows_miner.py" class="download-link">
            <span class="platform-badge">WIN</span>
            rustchain_windows_miner.py
            <span class="file-size">7.9 KB</span>
        </a>
        <p><strong>Supported</strong>: Windows 10/11 (64-bit)</p>
        <p><strong>Power</strong>: 1.0x base (Modern Tier)</p>
        <p><strong>Run</strong>: <code>python rustchain_windows_miner.py</code></p>
    </div>

    <h2>🚀 Quick Start</h2>
    <div class="download-section">
        <h3>1. Install Python 3</h3>
        <p>Most systems come with Python. Test: <code>python3 --version</code></p>
        
        <h3>2. Install requests library</h3>
        <p><code>pip3 install requests</code></p>
        
        <h3>3. Run your miner</h3>
        <p><code>python3 rustchain_linux_miner.py</code></p>
        
        <h3>4. Specify wallet (optional)</h3>
        <p><code>python3 rustchain_linux_miner.py --wallet YOUR_WALLET_HERE</code></p>
    </div>

    <h2>📊 Network Stats</h2>
    <div class="download-section">
        <p><a href="https://rustchain.org/api/stats" style="color: #00ff00;">https://rustchain.org/api/stats</a></p>
        <p><a href="https://rustchain.org/api/miners" style="color: #00ff00;">https://rustchain.org/api/miners</a></p>
    </div>

    <h2>💬 Community</h2>
    <div class="download-section">
        <p><strong>Discord</strong>: Ask Stephen Reed for invite link</p>
        <p><strong>GitHub</strong>: Coming soon</p>
    </div>

    <hr style="border-color: #00ff00; margin: 40px 0;">
    <p style="text-align: center; color: #888;">
        "Mining with history, not electricity" | RustChain v2.2.1
    </p>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/downloads/<path:filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    print(f"🦀 RustChain Download Server starting on port 8090...")
    print(f"📁 Serving files from: {DOWNLOAD_DIR}")
    print(f"🌐 Access at: https://rustchain.org:8090")
    app.run(host='0.0.0.0', port=8090, debug=False)
