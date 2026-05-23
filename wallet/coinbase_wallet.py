"""
ClawRTC Coinbase Wallet Integration
Optional module for creating/managing Coinbase Base wallets.

Install with: pip install clawrtc[coinbase]
"""

import json
import os
import socket
import sys
import time
from typing import Dict, Any, Optional, Tuple

import requests

# ANSI colors (match cli.py)
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

# Current public RustChain host. Older helper builds referenced a retired
# metalseed hostname, which can surface as a false "could not reach network"
# error even when the public node is healthy.
NODE_URL = "https://rustchain.org"

SWAP_INFO = {
    "wrtc_contract": "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
    "usdc_contract": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "aerodrome_pool": "0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F",
    "swap_url": "https://aerodrome.finance/swap?from=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&to=0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
    "network": "Base (eip155:8453)",
    "reference_price_usd": 0.10,
}

INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".clawrtc")
COINBASE_FILE = os.path.join(INSTALL_DIR, "coinbase_wallet.json")

# Retry configuration
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 8.0


def _check_network_connectivity(url: str) -> Tuple[bool, str]:
    """Check whether the network is reachable via DNS + TCP.

    Returns (is_reachable, error_message).
    """
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or url
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        return False, f"DNS resolution failed for {host}"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        if result != 0:
            return False, f"Cannot connect to {host}:{port} (error {result})"
    except OSError as exc:
        return False, f"Cannot connect to {host}:{port}: {exc}"

    return True, ""


def _fetch_with_retry(
    url: str,
    max_retries: int = 3,
    timeout: int = 15,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Fetch JSON from *url* with exponential-backoff retry.

    Returns (data, error_message).  On success error_message is ``None``.
    """
    last_error: Optional[Exception] = None
    delay = INITIAL_RETRY_DELAY

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, verify=True)
            resp.raise_for_status()
            return resp.json(), None
        except requests.exceptions.ConnectionError as exc:
            last_error = exc
            is_reachable, diag = _check_network_connectivity(url)
            if not is_reachable:
                return None, f"Network unreachable: {diag}"
        except requests.exceptions.Timeout as exc:
            last_error = exc
            return None, f"Request timeout after {timeout}s (tried {max_retries}x)"
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            return None, f"API error: HTTP {status}"
        except Exception as exc:
            last_error = exc

        if attempt < max_retries:
            # Use monotonic sleep to ensure reliable backoff timing
            target = time.monotonic() + delay
            while time.monotonic() < target:
                time.sleep(min(0.005, target - time.monotonic()))
            delay = min(delay * 2, MAX_RETRY_DELAY)

    # All retries exhausted — build a descriptive message
    if last_error is not None:
        return None, f"Request failed after {max_retries} retries: {last_error}"
    return None, f"Request failed after {max_retries} retries"


def _get_wallet_balance_from_node(
    address: str,
) -> Tuple[Optional[float], Optional[str]]:
    """Fetch wallet balance from the RustChain public node.

    Returns (balance, error_message).
    """
    url = f"{NODE_URL}/wallet/balance?address={address}"
    data, error = _fetch_with_retry(url)
    if error:
        return None, error

    if not isinstance(data, dict):
        return None, "Invalid response format from node"

    # Try common field names
    for key in ("balance", "amount_rtc", "amount"):
        val = data.get(key)
        if val is not None:
            try:
                return float(val), None
            except (TypeError, ValueError):
                return None, f"Invalid balance format: {val!r}"

    return None, "Balance not found in node response"


def _load_coinbase_wallet():
    """Load saved Coinbase wallet data."""
    if not os.path.exists(COINBASE_FILE):
        return None
    try:
        with open(COINBASE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_coinbase_wallet(data):
    """Save Coinbase wallet data to disk."""
    os.makedirs(INSTALL_DIR, exist_ok=True)
    with open(COINBASE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(COINBASE_FILE, 0o600)


def coinbase_create(args):
    """Create a Coinbase Base wallet via AgentKit."""
    existing = _load_coinbase_wallet()
    if existing and not getattr(args, "force", False):
        print(f"\n  {YELLOW}You already have a Coinbase wallet:{NC}")
        print(f"  {GREEN}{BOLD}{existing['address']}{NC}")
        print(f"  Network: {existing.get('network', 'Base')}")
        print(f"\n  To create a new one: clawrtc wallet coinbase create --force\n")
        return

    # Check for CDP credentials
    cdp_key_name = os.environ.get("CDP_API_KEY_NAME", "")
    cdp_key_private = os.environ.get("CDP_API_KEY_PRIVATE_KEY", "")

    if not cdp_key_name or not cdp_key_private:
        print(f"""
  {YELLOW}Coinbase CDP credentials not configured.{NC}

  To create a wallet automatically:
    1. Sign up at {CYAN}https://portal.cdp.coinbase.com{NC}
    2. Create an API Key
    3. Set environment variables:
       export CDP_API_KEY_NAME="organizations/.../apiKeys/..."
       export CDP_API_KEY_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----..."

  Or link an existing Base address manually:
    clawrtc wallet coinbase link 0xYourBaseAddress
""")
        return

    try:
        from coinbase_agentkit import AgentKit, AgentKitConfig

        print(f"  {CYAN}Creating Coinbase wallet on Base...{NC}")

        config = AgentKitConfig(
            cdp_api_key_name=cdp_key_name,
            cdp_api_key_private_key=cdp_key_private,
            network_id="base-mainnet",
        )
        kit = AgentKit(config)
        wallet = kit.wallet
        address = wallet.default_address.address_id

        wallet_data = {
            "address": address,
            "network": "Base (eip155:8453)",
            "created": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "method": "agentkit",
        }
        _save_coinbase_wallet(wallet_data)

        print(f"""
  {GREEN}{BOLD}═══════════════════════════════════════════════════════════
    COINBASE BASE WALLET CREATED
  ═══════════════════════════════════════════════════════════{NC}

  {GREEN}Base Address:{NC}  {BOLD}{address}{NC}
  {DIM}Network:{NC}       Base (eip155:8453)
  {DIM}Saved to:{NC}      {COINBASE_FILE}

  {CYAN}What you can do:{NC}
    - Receive USDC payments via x402 protocol
    - Swap USDC → wRTC on Aerodrome DEX
    - Link to your RustChain miner for cross-chain identity
    - See swap info: clawrtc wallet coinbase swap-info
""")
    except ImportError:
        print(f"""
  {RED}coinbase-agentkit not installed.{NC}

  Install it with:
    pip install clawrtc[coinbase]

  Or: pip install coinbase-agentkit
""")
    except Exception as e:
        print(f"\n  {RED}Failed to create wallet: {e}{NC}\n")


def coinbase_show(args):
    """Show Coinbase Base wallet info."""
    wallet = _load_coinbase_wallet()
    if not wallet:
        print(f"\n  {YELLOW}No Coinbase wallet found.{NC}")
        print(f"  Create one: clawrtc wallet coinbase create")
        print(f"  Or link:    clawrtc wallet coinbase link 0xYourAddress\n")
        return

    print(f"\n  {GREEN}{BOLD}Coinbase Base Wallet{NC}")
    print(f"  {GREEN}Address:{NC}    {BOLD}{wallet['address']}{NC}")
    print(f"  {DIM}Network:{NC}    {DIM}{wallet.get('network', 'Base')}{NC}")
    print(f"  {DIM}Created:{NC}    {DIM}{wallet.get('created', 'unknown')}{NC}")
    print(f"  {DIM}Method:{NC}     {DIM}{wallet.get('method', 'unknown')}{NC}")
    print(f"  {DIM}Key File:{NC}   {DIM}{COINBASE_FILE}{NC}")

    # Fetch live balance from the RustChain node
    balance, error = _get_wallet_balance_from_node(wallet["address"])
    if error:
        print(f"  {YELLOW}Balance:{NC}    {YELLOW}(could not fetch){NC}")
        print(f"  {DIM}Unable to fetch balance: {error}{NC}")
        is_reachable, diag = _check_network_connectivity(NODE_URL)
        if not is_reachable:
            print(f"  {DIM}Network unreachable: {diag}{NC}")
        print(f"  {DIM}Troubleshooting: see wallet/NETWORK_ERROR_HANDLING.md{NC}")
    else:
        print(f"  {GREEN}Balance:{NC}    {GREEN}{BOLD}{balance:0.8f}{NC} wRTC")

    print()


def coinbase_link(args):
    """Link an existing Base address as your Coinbase wallet."""
    address = getattr(args, "base_address", "")
    if not address:
        print(f"\n  {YELLOW}Usage: clawrtc wallet coinbase link 0xYourBaseAddress{NC}\n")
        return

    if not address.startswith("0x") or len(address) != 42:
        print(f"\n  {RED}Invalid Base address. Must be 0x + 40 hex characters.{NC}\n")
        return

    wallet_data = {
        "address": address,
        "network": "Base (eip155:8453)",
        "created": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "method": "manual_link",
    }
    _save_coinbase_wallet(wallet_data)

    print(f"\n  {GREEN}Coinbase wallet linked:{NC} {BOLD}{address}{NC}")
    print(f"  {DIM}Saved to: {COINBASE_FILE}{NC}")

    # Also try to link to RustChain miner
    rtc_wallet_file = os.path.join(INSTALL_DIR, "wallets", "default.json")
    if os.path.exists(rtc_wallet_file):
        try:
            with open(rtc_wallet_file) as f:
                rtc = json.load(f)
            print(f"  {DIM}Linked to RTC wallet: {rtc['address']}{NC}")
        except Exception:
            pass
    print()


def coinbase_swap_info(args):
    """Show USDC→wRTC swap instructions and Aerodrome pool info."""
    print(f"""
  {GREEN}{BOLD}USDC → wRTC Swap Guide{NC}

  {CYAN}wRTC Contract (Base):{NC}
    {BOLD}{SWAP_INFO['wrtc_contract']}{NC}

  {CYAN}USDC Contract (Base):{NC}
    {BOLD}{SWAP_INFO['usdc_contract']}{NC}

  {CYAN}Aerodrome Pool:{NC}
    {BOLD}{SWAP_INFO['aerodrome_pool']}{NC}

  {CYAN}Swap URL:{NC}
    {BOLD}{SWAP_INFO['swap_url']}{NC}

  {CYAN}Network:{NC} {SWAP_INFO['network']}
  {CYAN}Reference Price:{NC} ~${SWAP_INFO['reference_price_usd']}/wRTC

  {GREEN}How to swap:{NC}
    1. Get USDC on Base (bridge from Ethereum or buy on Coinbase)
    2. Go to the Aerodrome swap URL above
    3. Connect your wallet (MetaMask, Coinbase Wallet, etc.)
    4. Swap USDC for wRTC
    5. Bridge wRTC to native RTC at https://bottube.ai/bridge

  {DIM}Or use the RustChain API:{NC}
    curl -s {NODE_URL}/wallet/swap-info
""")


def cmd_coinbase(args):
    """Handle clawrtc wallet coinbase subcommand."""
    action = getattr(args, "coinbase_action", None) or "show"

    dispatch = {
        "create": coinbase_create,
        "show": coinbase_show,
        "link": coinbase_link,
        "swap-info": coinbase_swap_info,
    }

    func = dispatch.get(action)
    if func:
        func(args)
    else:
        print(f"  Usage: clawrtc wallet coinbase [create|show|link|swap-info]")
