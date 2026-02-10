import requests
import json
import csv
import click
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODE_URL = "https://50.28.86.131"

def fetch_api_data(endpoint):
    return requests.get(f"{NODE_URL}{endpoint}", verify=False).json()

@click.command()
@click.option('--format', type=click.Choice(['csv', 'json']), default='csv', help="Export format.")
@click.option('--output', default='export', help="Output filename (without extension).")
def export_data(format, output):
    """Export RustChain network data for reporting and analytics."""
    click.echo(f"[*] Exporting data from {NODE_URL}...")
    
    # 1. Fetch Miners Data
    miners = fetch_api_data("/api/miners")
    
    # 2. Add Balance Info
    full_data = []
    for m in miners:
        mid = m['miner']
        try:
            balance = requests.get(f"{NODE_URL}/wallet/balance?miner_id={mid}", verify=False).json()
            m['balance_rtc'] = balance.get('amount_rtc', 0)
        except:
            m['balance_rtc'] = 0
        full_data.append(m)

    if format == 'json':
        with open(f"{output}.json", 'w') as f:
            json.dump(full_data, f, indent=2)
        click.echo(f"[✓] Data exported to {output}.json")
    
    else: # CSV
        if not full_data:
            click.echo("No data to export.")
            return
            
        keys = full_data[0].keys()
        with open(f"{output}.csv", 'w', newline='') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(full_data)
        click.echo(f"[✓] Data exported to {output}.csv")

if __name__ == "__main__":
    export_data()
