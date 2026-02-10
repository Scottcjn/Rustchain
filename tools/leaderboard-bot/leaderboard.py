import requests
import json
import click
import urllib3
from typing import List, Dict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODE_URL = "https://50.28.86.131"

def get_leaderboard_data():
    miners = requests.get(f"{NODE_URL}/api/miners", verify=False).json()
    
    leaderboard = []
    arch_stats = {}
    
    click.echo(f"Fetching balances for {len(miners)} miners...")
    for m in miners:
        mid = m['miner']
        arch = m.get('device_arch', 'unknown')
        
        # Arch Distribution
        arch_stats[arch] = arch_stats.get(arch, 0) + 1
        
        # Balance
        try:
            b_data = requests.get(f"{NODE_URL}/wallet/balance?miner_id={mid}", verify=False).json()
            balance = b_data.get('amount_rtc', 0)
        except:
            balance = 0
            
        leaderboard.append({
            "miner": mid,
            "balance": balance,
            "arch": arch,
            "multiplier": m.get('antiquity_multiplier', 1.0)
        })
    
    # Sort by balance
    leaderboard.sort(key=lambda x: x['balance'], reverse=True)
    return leaderboard, arch_stats

@click.command()
@click.option('--webhook', help="Discord Webhook URL to post the leaderboard.")
def run_bot(webhook):
    """Generate and post RustChain mining leaderboard."""
    data, archs = get_leaderboard_data()
    
    # Format Discord Message
    msg = "**🏆 RustChain Mining Leaderboard 🏆**\n\n"
    msg += "```\nRank | Miner ID                     | Balance    | Arch\n"
    msg += "-----|------------------------------|------------|------\n"
    
    for i, entry in enumerate(data[:10]):
        rank = str(i+1).ljust(4)
        miner = (entry['miner'][:28] + "..") if len(entry['miner']) > 28 else entry['miner'].ljust(30)
        balance = f"{entry['balance']:>10.2f}"
        msg += f"{rank} | {miner} | {balance} | {entry['arch']}\n"
    
    msg += "```\n"
    
    msg += "**Network Stats:**\n"
    msg += f"• Total Active Miners: {len(data)}\n"
    for arch, count in archs.items():
        msg += f"• {arch.upper()}: {count} ({int(count/len(data)*100)}%)\n"

    if webhook:
        requests.post(webhook, json={"content": msg})
        click.echo("Leaderboard posted to Discord.")
    else:
        click.echo(msg)

if __name__ == "__main__":
    run_bot()
