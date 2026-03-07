#!/usr/bin/env python3
"""
RustChain Health Check CLI
Queries all 3 attestation nodes and displays health status.
"""

import json
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from tabulate import tabulate

NODES = [
    ("Node 1", "50.28.86.131", 443),
    ("Node 2", "50.28.86.153", 443),
    ("Node 3", "76.8.228.245", 8099),
]

# Create SSL context that doesn't verify certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def check_node(name, host, port):
    """Check health of a single node."""
    url = f"https://{host}:{port}/health"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
            data = json.loads(response.read().decode())
            return {
                "node": name,
                "status": "✅ Online" if data.get("ok") else "❌ Offline",
                "version": data.get("version", "N/A"),
                "uptime": format_uptime(data.get("uptime_s", 0)),
                "db_rw": "✅ RW" if data.get("db_rw") else "❌ RO",
                "tip_age": data.get("tip_age_slots", "N/A"),
            }
    except urllib.error.URLError as e:
        return {
            "node": name,
            "status": f"❌ Error: {str(e)[:40]}",
            "version": "-",
            "uptime": "-",
            "db_rw": "-",
            "tip_age": "-",
        }
    except Exception as e:
        return {
            "node": name,
            "status": f"❌ Error: {str(e)[:40]}",
            "version": "-",
            "uptime": "-",
            "db_rw": "-",
            "tip_age": "-",
        }

def format_uptime(seconds):
    """Format uptime in human-readable format."""
    if seconds == 0:
        return "N/A"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def main():
    print("\n" + "="*60)
    print("🔍 RustChain Health Check")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*60 + "\n")
    
    results = []
    for name, host, port in NODES:
        result = check_node(name, host, port)
        results.append(result)
    
    table_data = [
        [
            r["node"],
            r["status"],
            r["version"],
            r["uptime"],
            r["db_rw"],
            r["tip_age"],
        ]
        for r in results
    ]
    
    headers = ["Node", "Status", "Version", "Uptime", "DB RW", "Tip Age (slots)"]
    print(tabulate(table_data, headers=headers, tablefmt="github"))
    print()

if __name__ == "__main__":
    main()
