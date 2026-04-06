#!/usr/bin/env python3
"""
PPA Attestation Visualizer
==========================
Renders RustChain's 7-channel PPA fingerprint as a visual hardware identity card.

Usage:
    python ppa_visualizer.py fingerprint_output.json
    python ppa_visualizer.py fingerprint_output.json --output badge.html
    python ppa_visualizer.py fingerprint_output.json --format svg

Output formats: html (default), svg, png
"""

import argparse
import json
import math
import sys
from typing import Dict, List, Optional, Tuple
from pathlib import Path


def generate_radar_chart(checks_data: Dict, width: int = 300, height: int = 300) -> str:
    """Generate SVG radar chart for 7 PPA channels."""
    channels = [
        ("Clock Drift", "clock_drift"),
        ("Cache Timing", "cache_timing"),
        ("SIMD Identity", "simd_identity"),
        ("Thermal Drift", "thermal_drift"),
        ("Instruction Jitter", "instruction_jitter"),
        ("Anti-Emulation", "anti_emulation"),
        ("Device Age", "device_age"),
    ]
    
    # Calculate scores (0-100) for each channel
    scores = []
    for label, key in channels:
        if key in checks_data:
            check = checks_data[key]
            if isinstance(check, dict):
                passed = check.get("passed", check.get("valid", False))
                scores.append(100 if passed else 30)
            else:
                scores.append(50)
        else:
            scores.append(50)  # Unknown
    
    center_x, center_y = width // 2, height // 2
    radius = min(width, height) // 2 - 40
    num_channels = len(channels)
    
    # Generate polygon points
    points = []
    for i, score in enumerate(scores):
        angle = (2 * math.pi * i / num_channels) - math.pi / 2
        r = radius * (score / 100)
        x = center_x + r * math.cos(angle)
        y = center_y + r * math.sin(angle)
        points.append(f"{x},{y}")
    
    polygon_points = " ".join(points)
    
    # Generate axis lines and labels
    axis_lines = []
    labels = []
    for i, (label, _) in enumerate(channels):
        angle = (2 * math.pi * i / num_channels) - math.pi / 2
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        axis_lines.append(f'<line x1="{center_x}" y1="{center_y}" x2="{x}" y2="{y}" stroke="#333" stroke-width="1"/>')
        
        # Label position
        label_x = center_x + (radius + 25) * math.cos(angle)
        label_y = center_y + (radius + 25) * math.sin(angle)
        anchor = "middle"
        if label_x < center_x - 10:
            anchor = "end"
        elif label_x > center_x + 10:
            anchor = "start"
        labels.append(f'<text x="{label_x}" y="{label_y}" text-anchor="{anchor}" font-size="10" fill="#666">{label}</text>')
    
    # Generate concentric circles (25%, 50%, 75%, 100%)
    circles = []
    for pct in [25, 50, 75, 100]:
        r = radius * (pct / 100)
        circles.append(f'<circle cx="{center_x}" cy="{center_y}" r="{r}" fill="none" stroke="#ddd" stroke-width="1"/>')
    
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#fafafa"/>
        {''.join(circles)}
        {''.join(axis_lines)}
        <polygon points="{polygon_points}" fill="rgba(0, 230, 118, 0.3)" stroke="#00E676" stroke-width="2"/>
        {''.join(labels)}
    </svg>'''
    
    return svg


def generate_hardware_badge(fingerprint_data: Dict, width: int = 400, height: int = 200) -> str:
    """Generate visual hardware identity badge (GitHub identicon style)."""
    # Create deterministic hash from device info
    device = fingerprint_data.get("device", {})
    device_family = device.get("device_family", "Unknown")
    device_arch = device.get("device_arch", "unknown")
    cores = device.get("cores", 0)
    
    # Generate color from arch hash
    hash_input = f"{device_family}:{device_arch}:{cores}"
    hash_val = hash(hash_input) % 360
    hue1 = hash_val
    hue2 = (hash_val + 40) % 360
    
    # Create pattern based on cores and architecture
    pattern_seed = cores + len(device_arch)
    
    # Generate SVG badge
    svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:hsl({hue1}, 70%, 50%)"/>
                <stop offset="100%" style="stop-color:hsl({hue2}, 70%, 50%)"/>
            </linearGradient>
        </defs>
        <rect width="100%" height="100%" rx="10" fill="url(#grad)"/>
        <rect x="10" y="10" width="{width-20}" height="{height-20}" rx="8" fill="rgba(255,255,255,0.95)"/>
        <text x="{width//2}" y="50" text-anchor="middle" font-size="24" font-weight="bold" fill="#333">{device_family}</text>
        <text x="{width//2}" y="80" text-anchor="middle" font-size="16" fill="#666">{device_arch.upper()}</text>
        <text x="{width//2}" y="110" text-anchor="middle" font-size="14" fill="#999">{cores} Cores</text>
        <circle cx="{width//2}" cy="{height-40}" r="15" fill="hsl({hue1}, 70%, 50%)"/>
        <text x="{width//2}" y="{height-35}" text-anchor="middle" font-size="10" fill="white" font-weight="bold">PPA</text>
    </svg>'''
    
    return svg


def generate_html_report(fingerprint_data: Dict, output_path: str):
    """Generate full HTML report with all visualizations."""
    checks = fingerprint_data.get("fingerprint", {}).get("checks", {})
    device = fingerprint_data.get("device", {})
    
    radar_svg = generate_radar_chart(checks, 350, 350)
    badge_svg = generate_hardware_badge(fingerprint_data, 400, 200)
    
    # Calculate overall score
    total_checks = len(checks)
    passed_checks = sum(1 for check in checks.values() if isinstance(check, dict) and (check.get("passed") or check.get("valid")))
    score_pct = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    
    # Status color
    if score_pct >= 80:
        status_color = "#00E676"
        status_text = "PPA COMPLIANT"
    elif score_pct >= 50:
        status_color = "#FFB300"
        status_text = "PPA PARTIAL"
    else:
        status_color = "#FF5252"
        status_text = "NON-COMPLIANT"
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PPA Attestation Visualizer</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            padding: 40px;
            min-height: 100vh;
            margin: 0;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            font-weight: 300;
            letter-spacing: 2px;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 40px;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            align-items: center;
        }}
        @media (max-width: 700px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
        .status {{
            text-align: center;
            padding: 20px;
            border-radius: 12px;
            background: {status_color}20;
            border: 2px solid {status_color};
        }}
        .status-text {{
            font-size: 24px;
            font-weight: bold;
            color: {status_color};
        }}
        .status-score {{
            font-size: 48px;
            font-weight: bold;
            color: {status_color};
            margin: 10px 0;
        }}
        .checks-list {{
            margin-top: 20px;
        }}
        .check-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .check-pass {{ color: #00E676; }}
        .check-fail {{ color: #FF5252; }}
        .check-unknown {{ color: #888; }}
        svg {{
            display: block;
            margin: 0 auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 PPA ATTESTATION</h1>
        <p class="subtitle">Proof of Physical AI — Hardware Fingerprint Visualization</p>
        
        <div class="grid">
            <div class="card">
                {badge_svg}
            </div>
            <div class="card">
                <div class="status">
                    <div class="status-text">{status_text}</div>
                    <div class="status-score">{score_pct:.0f}%</div>
                    <div>{passed_checks}/{total_checks} checks passed</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h3 style="text-align:center;margin-bottom:20px;">Channel Performance Radar</h3>
            {radar_svg}
        </div>
        
        <div class="card">
            <h3>Detailed Check Results</h3>
            <div class="checks-list">
'''
    
    # Add check details
    for check_name, check_data in checks.items():
        if isinstance(check_data, dict):
            passed = check_data.get("passed", check_data.get("valid", False))
            status_class = "check-pass" if passed else "check-fail"
            status_icon = "✓" if passed else "✗"
        else:
            status_class = "check-unknown"
            status_icon = "?"
        
        check_label = check_name.replace("_", " ").title()
        html += f'                <div class="check-item"><span>{check_label}</span><span class="{status_class}">{status_icon}</span></div>\n'
    
    html += '''            </div>
        </div>
        
        <div style="text-align:center;color:#666;margin-top:40px;">
            Generated by PPA Attestation Visualizer v1.0
        </div>
    </div>
</body>
</html>'''
    
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ HTML report generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='PPA Attestation Visualizer')
    parser.add_argument('input', help='Input JSON file from fingerprint_checks.py')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--format', '-f', choices=['html', 'svg', 'png'], default='html',
                       help='Output format (default: html)')
    args = parser.parse_args()
    
    # Load fingerprint data
    with open(args.input, 'r') as f:
        fingerprint_data = json.load(f)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.input)
        output_path = input_path.with_suffix(f'.{args.format}')
    
    # Generate output
    if args.format == 'html':
        generate_html_report(fingerprint_data, str(output_path))
    elif args.format == 'svg':
        checks = fingerprint_data.get("fingerprint", {}).get("checks", {})
        svg = generate_radar_chart(checks, 400, 400)
        with open(output_path, 'w') as f:
            f.write(svg)
        print(f"✅ SVG radar chart generated: {output_path}")
    elif args.format == 'png':
        print("❌ PNG format requires additional dependencies (PIL/cairosvg)")
        print("   Use --format svg or html instead")
        sys.exit(1)
    
    print(f"\n🎯 View: file://{Path(output_path).absolute()}")


if __name__ == '__main__':
    main()
