// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

from flask import Flask, jsonify, render_template_string
import json
import os
import platform
import re
import subprocess
import sys

app = Flask(__name__)

SILICON_EPOCHS = {
    0: {"years": (1970, 1979), "multiplier": 10.0, "description": "Ancient Silicon"},
    1: {"years": (1980, 1989), "multiplier": 8.0, "description": "Classic Era"},
    2: {"years": (1990, 1999), "multiplier": 6.0, "description": "Rise of PC"},
    3: {"years": (2000, 2009), "multiplier": 4.0, "description": "Multi-core Dawn"},
    4: {"years": (2010, 2024), "multiplier": 2.0, "description": "Modern Silicon"}
}

CPU_DATABASE = {
    # Ancient Silicon (1970-1979)
    "8008": {"year": 1972, "epoch": 0},
    "8080": {"year": 1974, "epoch": 0},
    "6502": {"year": 1975, "epoch": 0},
    "z80": {"year": 1976, "epoch": 0},
    "6800": {"year": 1974, "epoch": 0},

    # Classic Era (1980-1989)
    "8086": {"year": 1978, "epoch": 1},
    "8088": {"year": 1979, "epoch": 1},
    "80286": {"year": 1982, "epoch": 1},
    "68000": {"year": 1979, "epoch": 1},
    "68020": {"year": 1984, "epoch": 1},
    "80386": {"year": 1985, "epoch": 1},

    # Rise of PC (1990-1999)
    "80486": {"year": 1989, "epoch": 2},
    "pentium": {"year": 1993, "epoch": 2},
    "pentium pro": {"year": 1995, "epoch": 2},
    "pentium ii": {"year": 1997, "epoch": 2},
    "pentium iii": {"year": 1999, "epoch": 2},
    "k6": {"year": 1997, "epoch": 2},
    "athlon": {"year": 1999, "epoch": 2},
    "powerpc 601": {"year": 1993, "epoch": 2},
    "powerpc 603": {"year": 1994, "epoch": 2},
    "powerpc 604": {"year": 1994, "epoch": 2},
    "powerpc 750": {"year": 1997, "epoch": 2},

    # Multi-core Dawn (2000-2009)
    "pentium 4": {"year": 2000, "epoch": 3},
    "athlon 64": {"year": 2003, "epoch": 3},
    "core duo": {"year": 2006, "epoch": 3},
    "core 2": {"year": 2006, "epoch": 3},
    "powerpc 970": {"year": 2003, "epoch": 3},
    "powerpc g5": {"year": 2003, "epoch": 3},

    # Modern Silicon (2010+)
    "core i3": {"year": 2010, "epoch": 4},
    "core i5": {"year": 2009, "epoch": 4},
    "core i7": {"year": 2008, "epoch": 4},
    "ryzen": {"year": 2017, "epoch": 4},
    "apple m1": {"year": 2020, "epoch": 4},
    "apple m2": {"year": 2022, "epoch": 4}
}

def detect_cpu_linux():
    """Extract CPU info from /proc/cpuinfo on Linux"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            content = f.read().lower()

        model_name = ""
        for line in content.split('\n'):
            if 'model name' in line:
                model_name = line.split(':')[1].strip()
                break

        return model_name
    except:
        return ""

def detect_cpu_macos():
    """Get CPU info using sysctl on macOS"""
    try:
        result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                              capture_output=True, text=True)
        return result.stdout.strip().lower()
    except:
        try:
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'],
                                  capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'processor name' in line.lower():
                    return line.split(':')[1].strip().lower()
        except:
            pass
    return ""

def detect_cpu_generic():
    """Fallback CPU detection using platform module"""
    try:
        return platform.processor().lower()
    except:
        return ""

def classify_cpu(cpu_string):
    """Classify CPU into silicon epoch based on detection"""
    cpu_lower = cpu_string.lower()

    # Direct matches first
    for cpu_key, data in CPU_DATABASE.items():
        if cpu_key in cpu_lower:
            return {
                "family": cpu_key,
                "model": cpu_string,
                "epoch": data["epoch"],
                "year_estimate": data["year"],
                "rustchain_multiplier": SILICON_EPOCHS[data["epoch"]]["multiplier"]
            }

    # Pattern matching for complex names
    patterns = [
        (r'apple m[12]', "apple m1", 4, 2020),
        (r'ryzen \d+', "ryzen", 4, 2017),
        (r'core i[3579]', "core i7", 4, 2008),
        (r'core 2', "core 2", 3, 2006),
        (r'pentium.*4', "pentium 4", 3, 2000),
        (r'pentium.*iii', "pentium iii", 2, 1999),
        (r'pentium.*ii', "pentium ii", 2, 1997),
        (r'pentium(?!.*[ii])', "pentium", 2, 1993),
        (r'athlon.*64', "athlon 64", 3, 2003),
        (r'athlon', "athlon", 2, 1999),
        (r'powerpc|power.*pc', "powerpc", 2, 1993),
        (r'486|80486', "80486", 2, 1989),
        (r'386|80386', "80386", 1, 1985),
        (r'286|80286', "80286", 1, 1982),
        (r'8086', "8086", 1, 1978)
    ]

    for pattern, family, epoch, year in patterns:
        if re.search(pattern, cpu_lower):
            return {
                "family": family,
                "model": cpu_string,
                "epoch": epoch,
                "year_estimate": year,
                "rustchain_multiplier": SILICON_EPOCHS[epoch]["multiplier"]
            }

    # Unknown CPU - classify as modern by default
    return {
        "family": "unknown",
        "model": cpu_string,
        "epoch": 4,
        "year_estimate": 2020,
        "rustchain_multiplier": SILICON_EPOCHS[4]["multiplier"]
    }

def scan_hardware():
    """Main hardware scanning function"""
    system = platform.system().lower()

    if system == "linux":
        cpu_info = detect_cpu_linux()
    elif system == "darwin":
        cpu_info = detect_cpu_macos()
    else:
        cpu_info = detect_cpu_generic()

    if not cpu_info:
        cpu_info = "unknown processor"

    result = classify_cpu(cpu_info)
    result["detected_system"] = platform.system()
    result["platform_details"] = platform.platform()

    return result

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Silicon Archaeology Scanner</title>
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #00ff00; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .scan-box { border: 1px solid #00ff00; padding: 20px; margin: 20px 0; }
        .epoch-info { background: #1a1a1a; padding: 15px; margin: 15px 0; border-left: 4px solid #00ff00; }
        .json-output { background: #1a1a1a; padding: 15px; white-space: pre-wrap; font-size: 12px; border: 1px dashed #666; }
        button { background: #00ff00; color: #000; padding: 10px 20px; border: none; cursor: pointer; font-family: monospace; }
        button:hover { background: #00cc00; }
        .multiplier { color: #ffff00; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 SILICON ARCHAEOLOGY SCANNER</h1>
            <p>Hardware Fingerprinting & Epoch Classification</p>
        </div>

        <div class="scan-box">
            <h2>Current System Analysis</h2>
            <button onclick="scanSystem()">🔍 SCAN HARDWARE</button>
            <div id="results"></div>
        </div>

        <div class="epoch-info">
            <h3>Silicon Epochs Reference</h3>
            <ul>
                <li><strong>Epoch 0 (1970-1979):</strong> Ancient Silicon - 10x Rustchain multiplier</li>
                <li><strong>Epoch 1 (1980-1989):</strong> Classic Era - 8x multiplier</li>
                <li><strong>Epoch 2 (1990-1999):</strong> Rise of PC - 6x multiplier</li>
                <li><strong>Epoch 3 (2000-2009):</strong> Multi-core Dawn - 4x multiplier</li>
                <li><strong>Epoch 4 (2010-2024):</strong> Modern Silicon - 2x multiplier</li>
            </ul>
        </div>
    </div>

    <script>
        async function scanSystem() {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<p>🔄 Scanning hardware...</p>';

            try {
                const response = await fetch('/api/scan');
                const data = await response.json();

                let html = `
                    <h3>📊 Scan Results</h3>
                    <p><strong>Family:</strong> ${data.family}</p>
                    <p><strong>Model:</strong> ${data.model}</p>
                    <p><strong>Silicon Epoch:</strong> ${data.epoch}</p>
                    <p><strong>Estimated Year:</strong> ${data.year_estimate}</p>
                    <p><strong>Rustchain Multiplier:</strong> <span class="multiplier">${data.rustchain_multiplier}x</span></p>
                    <p><strong>System:</strong> ${data.detected_system}</p>

                    <h4>Raw JSON Output:</h4>
                    <div class="json-output">${JSON.stringify(data, null, 2)}</div>
                `;

                resultsDiv.innerHTML = html;
            } catch (error) {
                resultsDiv.innerHTML = `<p>❌ Error: ${error.message}</p>`;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main web interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/scan')
def api_scan():
    """API endpoint to scan current system hardware"""
    try:
        scan_result = scan_hardware()
        return jsonify(scan_result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/epochs')
def api_epochs():
    """Get silicon epochs reference data"""
    return jsonify(SILICON_EPOCHS)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
