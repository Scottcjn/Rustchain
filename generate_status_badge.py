// SPDX-License-Identifier: MIT
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sqlite3
import json
from datetime import datetime, timedelta
import os

DB_PATH = "blockchain.db"

def get_network_status():
    """Get current network status from database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get active miners count
            cursor.execute("""
                SELECT COUNT(*) FROM miners
                WHERE last_seen > datetime('now', '-10 minutes')
            """)
            active_miners = cursor.fetchone()[0]

            # Get total registered miners
            cursor.execute("SELECT COUNT(*) FROM miners")
            total_miners = cursor.fetchone()[0]

            # Get attestation nodes count
            cursor.execute("""
                SELECT COUNT(*) FROM attestation_nodes
                WHERE last_heartbeat > datetime('now', '-5 minutes')
            """)
            active_nodes = cursor.fetchone()[0]

            # Get total nodes
            cursor.execute("SELECT COUNT(*) FROM attestation_nodes")
            total_nodes = cursor.fetchone()[0]

            return {
                'active_miners': active_miners,
                'total_miners': total_miners,
                'active_nodes': active_nodes,
                'total_nodes': total_nodes
            }
    except Exception as e:
        print(f"Database error: {e}")
        return None

def determine_status_color(stats):
    """Determine badge color based on network health"""
    if not stats:
        return "red"

    # Calculate health percentages
    miner_health = stats['active_miners'] / max(stats['total_miners'], 1) if stats['total_miners'] > 0 else 0
    node_health = stats['active_nodes'] / max(stats['total_nodes'], 1) if stats['total_nodes'] > 0 else 0

    overall_health = (miner_health + node_health) / 2

    if overall_health >= 0.8:
        return "brightgreen"
    elif overall_health >= 0.5:
        return "yellow"
    else:
        return "red"

def generate_badge_svg(stats):
    """Generate SVG badge for network status"""
    if not stats:
        status_text = "offline"
        color = "red"
    else:
        status_text = f"{stats['active_miners']}/{stats['total_miners']} miners · {stats['active_nodes']}/{stats['total_nodes']} nodes"
        color = determine_status_color(stats)

    # SVG template
    svg_template = f'''<svg xmlns="http://www.w3.org/2000/svg" width="220" height="20">
  <defs>
    <linearGradient id="workflow-fill" x1="50%" y1="0%" x2="50%" y2="100%">
      <stop stop-color="#444d56" offset="0%"></stop>
      <stop stop-color="#24292e" offset="100%"></stop>
    </linearGradient>
    <linearGradient id="state-fill" x1="50%" y1="0%" x2="50%" y2="100%">
      <stop stop-color="#34d058" offset="0%"></stop>
      <stop stop-color="#28a745" offset="100%"></stop>
    </linearGradient>
  </defs>
  <g fill="none" fill-rule="evenodd">
    <g font-family="'DejaVu Sans',Verdana,Geneva,sans-serif" font-size="11">
      <path id="workflow-bg" d="M0,3 C0,1.3431 1.3431,0 3,0 L77,0 L77,20 L3,20 C1.3431,20 0,18.6569 0,17 L0,3 Z" fill="url(#workflow-fill)" fill-rule="nonzero"></path>
      <path id="state-bg" d="M77,0 L217,0 C218.6569,0 220,1.3431 220,3 L220,17 C220,18.6569 218.6569,20 217,20 L77,20 L77,0 Z" fill="{get_color_gradient(color)}" fill-rule="nonzero"></path>
      <text fill="#fff" x="6" y="15" textLength="67" lengthAdjust="spacing">RustChain</text>
      <text fill="#fff" x="82" y="15" textLength="133" lengthAdjust="spacing">{status_text}</text>
    </g>
  </g>
</svg>'''

    return svg_template

def get_color_gradient(color):
    """Get gradient color definition for badge"""
    color_map = {
        "brightgreen": "url(#state-fill)",
        "green": "#4c9a2e",
        "yellow": "#dfb317",
        "orange": "#fe7d37",
        "red": "#e05d44",
        "lightgrey": "#9f9f9f"
    }
    return color_map.get(color, "#e05d44")

def main():
    """Generate and save status badge"""
    stats = get_network_status()
    svg_content = generate_badge_svg(stats)

    # Save to file
    with open('network_status_badge.svg', 'w') as f:
        f.write(svg_content)

    print("Network status badge generated: network_status_badge.svg")

    if stats:
        print(f"Active miners: {stats['active_miners']}/{stats['total_miners']}")
        print(f"Active nodes: {stats['active_nodes']}/{stats['total_nodes']}")
        print(f"Badge color: {determine_status_color(stats)}")

if __name__ == "__main__":
    main()
