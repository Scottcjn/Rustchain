import requests
import json
import click
import urllib3
from typing import Dict, List

# Disable SSL warnings for self-signed node certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODES = [
    "https://50.28.86.131",
    "https://50.28.86.153",
    "http://76.8.228.245:8099"
]

def fetch_node_data(node_url: str) -> Dict:
    data = {"url": node_url, "online": False}
    try:
        # 1. Health & Sync Status
        health = requests.get(f"{node_url}/health", verify=False, timeout=5).json()
        data["health"] = health
        data["online"] = True
        
        # 2. Epoch State
        epoch = requests.get(f"{node_url}/epoch", verify=False, timeout=5).json()
        data["epoch"] = epoch
        
        # 3. Miner List
        miners = requests.get(f"{node_url}/api/miners", verify=False, timeout=5).json()
        data["miners"] = {m['miner']: m for m in miners}
        
    except Exception as e:
        data["error"] = str(e)
    return data

@click.command()
@click.option('--json-output', is_flag=True, help="Output results as JSON.")
def validate(json_output):
    """Validate data consistency across all RustChain attestation nodes."""
    results = []
    for node in NODES:
        click.echo(f"[*] Querying node: {node}...", err=True)
        results.append(fetch_node_data(node))

    online_nodes = [r for r in results if r["online"]]
    
    if not online_nodes:
        click.echo("CRITICAL: All nodes are OFFLINE.")
        return

    # Comparison Logic
    discrepancies = []
    
    # 1. Compare Epochs
    epochs = [r["epoch"].get("epoch") for r in online_nodes if "epoch" in r]
    if len(set(epochs)) > 1:
        discrepancies.append({
            "type": "EPOCH_DESYNC",
            "details": {r["url"]: r["epoch"].get("epoch") for r in online_nodes}
        })

    # 2. Compare Miner Lists
    all_miner_ids = set()
    for r in online_nodes:
        if "miners" in r:
            all_miner_ids.update(r["miners"].keys())
    
    for miner_id in all_miner_ids:
        presences = {r["url"]: (miner_id in r.get("miners", {})) for r in online_nodes}
        if not all(presences.values()):
            discrepancies.append({
                "type": "MINER_LIST_INCONSISTENCY",
                "miner_id": miner_id,
                "presence": presences
            })

    # Cyber Security: Check for anomalous multipliers or entropy scores
    for r in online_nodes:
        if "miners" in r:
            for mid, mdata in r["miners"].items():
                if mdata.get("antiquity_multiplier", 0) > 2.5:
                    discrepancies.append({
                        "type": "SECURITY_ANOMALY",
                        "node": r["url"],
                        "miner": mid,
                        "issue": f"Invalid multiplier detected: {mdata.get('antiquity_multiplier')}"
                    })

    # Output Results
    if json_output:
        click.echo(json.dumps({"nodes": results, "discrepancies": discrepancies}, indent=2))
    else:
        click.echo("\n--- Consistency Report ---")
        if not discrepancies:
            click.echo("✅ ALL NODES IN SYNC")
        else:
            for d in discrepancies:
                click.echo(f"❌ {d['type']}: {d.get('details') or d.get('miner_id')}")
        
        click.echo(f"\nNodes Online: {len(online_nodes)}/{len(NODES)}")

if __name__ == "__main__":
    validate()
