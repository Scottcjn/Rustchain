"""
Fossil Record 鈥?Attestation Archaeology Visualizer
Flask server exposing RustChain attestation history for the D3.js stratigraphy view.
"""

import requests
import json
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__, template_folder='static', static_folder='static')

# RustChain node API base
NODE_URL = "http://50.28.86.131:8099"

# Architecture color palette (geological strata theme)
ARCH_COLORS = {
    "68k": "#3d2b1f",      # deep brown/obsidian
    "powerpc_g4": "#d4a017", # amber/gold
    "powerpc_g5": "#b87333", # copper
    "sparc": "#1a3a5c",     # deep ocean blue
    "power8": "#2f4f6f",    # slate/navy
    "alpha": "#4a5568",      # gray steel
    "itanium": "#718096",    # silver gray
    "arm": "#90cdf4",        # pale ice blue
    "risc_v": "#38b2ac",    # teal
    "x86": "#e2e8f0",       # pale gray (recent sediment)
    "unknown": "#a0aec0",    # neutral gray
}

ARCH_LABELS = {
    "68k": "68K (Motorola)",
    "powerpc_g4": "PowerPC G4",
    "powerpc_g5": "PowerPC G5",
    "sparc": "SPARC",
    "power8": "POWER8",
    "alpha": "DEC Alpha",
    "itanium": "Itanium",
    "arm": "ARM/SBC",
    "risc_v": "RISC-V",
    "x86": "x86/Modern",
    "unknown": "Unknown",
}

# Sort order (oldest at bottom)
ARCH_SORT_ORDER = ["68k", "alpha", "itanium", "powerpc_g4", "powerpc_g5", "sparc", "power8", "arm", "risc_v", "x86", "unknown"]


def get_arch_family(device_info):
    """Map device info string to architecture family."""
    d = device_info.lower()
    if "680" in d or "68k" in d or "mc680" in d or "amiga" in d or "atari" in d or "mac II" in d:
        return "68k"
    if "g4" in d or "powerpc 7" in d or "powerbook" in d or "imap" in d:
        return "powerpc_g4"
    if "g5" in d or "powerpc 9" in d or "powermac" in d:
        return "powerpc_g5"
    if "sparc" in d or "sun" in d or "ultra" in d or "t" in d or "blade" in d:
        return "sparc"
    if "power8" in d or "power 8" in d or "ibm" in d or "p8" in d:
        return "power8"
    if "alpha" in d or "dec" in d or "axp" in d:
        return "alpha"
    if "itanium" in d or "ia-64" in d or "hp integrity" in d:
        return "itanium"
    if "risc-v" in d or "riscv" in d or "starfive" in d or "sifive" in d or "milk-v" in d:
        return "risc_v"
    if "arm" in d or "raspberry" in d or "pine64" in d or "beaglebone" in d:
        return "arm"
    if "x86" in d or "intel" in d or "amd" in d or "xeon" in d:
        return "x86"
    return "unknown"


def fetch_attestations(epoch_start=0, epoch_end=None, limit=5000):
    """Fetch attestation history from RustChain node."""
    try:
        # Try epoch list endpoint
        url = f"{NODE_URL}/epochs"
        params = {"start": epoch_start, "limit": limit}
        if epoch_end:
            params["end"] = epoch_end
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("epochs", [])
    except Exception as e:
        print(f"Epoch API failed: {e}")
    
    # Try attestation endpoint
    try:
        url = f"{NODE_URL}/attestations"
        params = {"limit": limit}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Attestation API failed: {e}")
    
    return []


def build_timeline_data(attestations):
    """Build timeline/stratigraphy data from attestations."""
    if not attestations:
        # Return demo data when API is unreachable
        return build_demo_data()
    
    arch_epochs = {}
    for att in attestations:
        epoch = att.get("epoch", 0)
        device = att.get("device", att.get("miner_id", ""))
        arch = get_arch_family(device)
        
        if arch not in arch_epochs:
            arch_epochs[arch] = {}
        if epoch not in arch_epochs[arch]:
            arch_epochs[arch][epoch] = {"count": 0, "total_rtc": 0, "miners": set()}
        
        arch_epochs[arch][epoch]["count"] += 1
        arch_epochs[arch][epoch]["total_rtc"] += att.get("reward", 0)
        arch_epochs[arch][epoch]["miners"].add(att.get("miner_id", "unknown"))
    
    # Build stratigraphy layers
    layers = []
    all_epochs = set()
    for arch_data in arch_epochs.values():
        all_epochs.update(arch_data.keys())
    
    for arch in ARCH_SORT_ORDER:
        if arch not in arch_epochs:
            continue
        arch_data = arch_epochs[arch]
        
        for epoch in sorted(all_epochs):
            if epoch not in arch_data:
                continue
            info = arch_data[epoch]
            layers.append({
                "epoch": epoch,
                "arch": arch,
                "label": ARCH_LABELS.get(arch, arch),
                "count": info["count"],
                "rtc": info["total_rtc"],
                "miner_count": len(info["miners"]),
                "color": ARCH_COLORS.get(arch, "#888"),
            })
    
    return layers


def build_demo_data():
    """Build demo data showing the expected visualization structure."""
    import random
    random.seed(42)
    layers = []
    
    # Generate realistic demo data
    # Genesis to epoch 10000, various architectures over time
    arch_timeline = {
        "68k": (0, 200),          # Early adoption, 1994-1996
        "alpha": (50, 400),       # Mid-90s
        "itanium": (200, 800),    # Late 90s
        "powerpc_g4": (100, 3000), # Mac G4 era
        "powerpc_g5": (500, 5000), # Mac G5 / early PowerMac
        "sparc": (300, 4000),     # Sun SPARC stations
        "power8": (2000, 10000),   # IBM POWER8 introduction
        "arm": (3000, 10000),      # ARM SBCs
        "risc_v": (5000, 10000),  # RISC-V emergence
        "x86": (0, 10000),        # Always present, dominant
    }
    
    for arch, (start, end) in arch_timeline.items():
        for epoch in range(start, min(end + 1, 10000), random.randint(5, 20)):
            if random.random() < 0.85:
                count = random.randint(1, 50)
                rtc = random.randint(1, 500) * count
                layers.append({
                    "epoch": epoch,
                    "arch": arch,
                    "label": ARCH_LABELS.get(arch, arch),
                    "count": count,
                    "rtc": rtc,
                    "miner_count": random.randint(1, 10),
                    "color": ARCH_COLORS.get(arch, "#888"),
                })
    
    return layers


@app.route("/")
def index():
    return render_template("fossil_timeline.html")


@app.route("/api/timeline")
def timeline_api():
    """Return stratigraphy data for D3.js."""
    epoch_start = request.args.get("start", 0, type=int)
    epoch_end = request.args.get("end", None, type=int)
    limit = request.args.get("limit", 5000, type=int)
    
    attestations = fetch_attestations(epoch_start, epoch_end, limit)
    layers = build_timeline_data(attestations)
    
    return jsonify({
        "layers": layers,
        "colors": ARCH_COLORS,
        "labels": ARCH_LABELS,
        "arch_order": ARCH_SORT_ORDER,
    })


@app.route("/api/archs")
def archs_api():
    """Return architecture summary."""
    attestations = fetch_attestations(limit=10000)
    layers = build_timeline_data(attestations)
    
    archs = {}
    for layer in layers:
        arch = layer["arch"]
        if arch not in archs:
            archs[arch] = {"label": layer["label"], "color": layer["color"], 
                          "total_epochs": 0, "total_rtc": 0, "total_miners": 0}
        archs[arch]["total_epochs"] += 1
        archs[arch]["total_rtc"] += layer["rtc"]
    
    return jsonify(archs)


@app.route("/api/epochs/<int:epoch>")
def epoch_detail(epoch):
    """Return detail for a specific epoch."""
    try:
        r = requests.get(f"{NODE_URL}/epochs/{epoch}", timeout=5)
        if r.status_code == 200:
            return jsonify(r.json())
    except:
        pass
    return jsonify({"error": "Epoch not found"})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fossil Record Visualizer")
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--node-url", default=NODE_URL)
    args = parser.parse_args()
    NODE_URL = args.node_url
    app.run(host=args.host, port=args.port, debug=False)