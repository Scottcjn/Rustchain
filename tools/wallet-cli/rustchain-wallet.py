import click
import json
import os
import requests
import hashlib
from pathlib import Path
from rustchain_crypto_minimal import RustChainCrypto

# Configuração baseada nos arquivos do repositório
NODE_URL = "https://50.28.86.131"
VERIFY_SSL = False
WALLET_DIR = Path.home() / ".rustchain" / "wallets"

@click.group()
def cli():
    """RustChain Wallet CLI - Manage your RTC tokens from the terminal."""
    pass

@cli.command()
@click.argument('name')
def create(name):
    """Create a new wallet."""
    WALLET_DIR.mkdir(parents=True, exist_ok=True)
    wallet_path = WALLET_DIR / f"{name}.json"
    
    if wallet_path.exists():
        click.echo(f"Error: Wallet '{name}' already exists.")
        return

    priv_hex, pub_hex = RustChainCrypto.generate_keypair()
    address = RustChainCrypto.get_address(pub_hex)

    wallet_data = {
        "name": name,
        "address": address,
        "private_key": priv_hex,
        "public_key": pub_hex
    }

    with open(wallet_path, 'w') as f:
        json.dump(wallet_data, f, indent=2)

    click.echo(f"Wallet '{name}' created successfully!")
    click.echo(f"Address: {address}")
    click.echo("IMPORTANT: Backup your private key securely!")

@cli.command()
@click.argument('wallet_id')
def balance(wallet_id):
    """Check balance for a wallet ID or address."""
    try:
        r = requests.get(f"{NODE_URL}/wallet/balance?miner_id={wallet_id}", verify=VERIFY_SSL)
        data = r.json()
        click.echo(f"Wallet: {wallet_id}")
        click.echo(f"Balance: {data.get('amount_rtc', 0):.8f} RTC")
    except Exception as e:
        click.echo(f"Error fetching balance: {e}")

@cli.command()
@click.option('--from-wallet', required=True, help='Name of the local wallet to use.')
@click.option('--to', required=True, help='Recipient RTC address.')
@click.option('--amount', required=True, type=float, help='Amount in RTC.')
@click.option('--memo', default="Sent via Wallet CLI", help='Optional memo.')
def send(from_wallet, to, amount, memo):
    """Send RTC to another address (signed)."""
    wallet_path = WALLET_DIR / f"{from_wallet}.json"
    if not wallet_path.exists():
        click.echo(f"Error: Wallet '{from_wallet}' not found.")
        return

    with open(wallet_path, 'r') as f:
        wallet = json.load(f)

    click.echo(f"Signing transaction for {amount} RTC to {to}...")
    
    try:
        signed_tx = RustChainCrypto.sign_transaction(
            wallet['private_key'], to, amount, memo
        )
        
        r = requests.post(f"{NODE_URL}/wallet/transfer/signed", json=signed_tx, verify=VERIFY_SSL)
        result = r.json()
        
        if result.get("ok"):
            click.echo("Transaction sent successfully!")
            click.echo(f"New Balance: {result.get('sender_balance_rtc'):.8f} RTC")
        else:
            click.echo(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        click.echo(f"Transaction failed: {e}")

@cli.command()
@click.argument('wallet_id')
def history(wallet_id):
    """View transaction history for a wallet."""
    try:
        r = requests.get(f"{NODE_URL}/wallet/ledger?miner_id={wallet_id}", verify=VERIFY_SSL)
        data = r.json()
        if "transactions" in data and data["transactions"]:
            click.echo(f"--- Transaction History for {wallet_id} ---")
            for tx in data["transactions"][:10]:
                tx_type = "IN" if tx.get("to") == wallet_id else "OUT"
                click.echo(f"[{tx.get('timestamp', 'N/A')}] {tx_type} | {tx.get('amount_rtc', 0):.4f} RTC | Memo: {tx.get('memo', 'N/A')}")
        else:
            click.echo("No transactions found for this wallet.")
    except Exception as e:
        click.echo(f"Error fetching history: {e}")

@cli.command()
def network():
    """Show network status and active miners."""
    try:
        health = requests.get(f"{NODE_URL}/health", verify=VERIFY_SSL).json()
        epoch = requests.get(f"{NODE_URL}/epoch", verify=VERIFY_SSL).json()
        miners = requests.get(f"{NODE_URL}/api/miners", verify=VERIFY_SSL).json()
        
        click.echo("--- RustChain Network Status ---")
        click.echo(f"Status: {health.get('status', 'Unknown')}")
        click.echo(f"Current Epoch: {epoch.get('epoch', 'N/A')} (Slot: {epoch.get('slot', 'N/A')})")
        click.echo(f"Active Miners: {len(miners)}")
        click.echo(f"Epoch Pot: {epoch.get('epoch_pot', 0)} RTC")
    except Exception as e:
        click.echo(f"Error fetching network status: {e}")

if __name__ == '__main__':
    cli()
