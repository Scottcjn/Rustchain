"""
Shared x402 + Coinbase AgentKit configuration.
Deploy to: /root/shared/x402_config.py on .131 and .153

All prices start at "0" (free) to prove the flow works.
Change values when ready to charge real USDC.
"""

import os
import logging

log = logging.getLogger("x402")

# --- x402 Constants ---
X402_NETWORK = "eip155:8453"                     # Base mainnet (CAIP-2)
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"   # Native USDC on Base
WRTC_BASE = "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6"   # wRTC on Base
AERODROME_POOL = "0x4C2A0b915279f0C22EA766D58F9B815Ded2d2A3F"  # wRTC/WETH pool

# --- Facilitator ---
FACILITATOR_URL = "https://x402-facilitator.cdp.coinbase.com"  # Coinbase hosted
# Free tier: 1,000 tx/month

# --- Treasury Addresses (receive x402 payments) ---
BOTTUBE_TREASURY = os.environ.get("BOTTUBE_X402_ADDRESS", "")
BEACON_TREASURY = os.environ.get("BEACON_X402_ADDRESS", "")

# --- Pricing (in USDC atomic units, 6 decimals) ---
# ALL SET TO "0" INITIALLY — prove the flow works, charge later
# When ready to charge, update these values (1 USDC = 1,000,000 units)
PRICE_VIDEO_STREAM_PREMIUM = "0"    # Future: "100000" = $0.10
PRICE_API_BULK = "0"                # Future: "50000"  = $0.05
PRICE_BEACON_CONTRACT = "0"         # Future: "10000"  = $0.01
PRICE_BOUNTY_CLAIM = "0"            # Future: "5000"   = $0.005
PRICE_PREMIUM_ANALYTICS = "0"       # Future: "200000" = $0.20
PRICE_PREMIUM_EXPORT = "0"          # Future: "100000" = $0.10
PRICE_RELAY_REGISTER = "0"          # Future: "10000"  = $0.01
PRICE_REPUTATION_EXPORT = "0"       # Future: "50000"  = $0.05

# --- CDP Credentials (set via environment) ---
CDP_API_KEY_NAME = os.environ.get("CDP_API_KEY_NAME", "")
CDP_API_KEY_PRIVATE_KEY = os.environ.get("CDP_API_KEY_PRIVATE_KEY", "")

# --- Swap Info ---
SWAP_INFO = {
    "wrtc_contract": WRTC_BASE,
    "usdc_contract": USDC_BASE,
    "aerodrome_pool": AERODROME_POOL,
    "swap_url": f"https://aerodrome.finance/swap?from={USDC_BASE}&to={WRTC_BASE}",
    "network": "Base (eip155:8453)",
    "reference_price_usd": 0.10,
}


def is_free(price_str):
    """Check if a price is $0 (free mode)."""
    return price_str == "0" or price_str == ""


def has_cdp_credentials():
    """Check if CDP API credentials are configured."""
    return bool(CDP_API_KEY_NAME and CDP_API_KEY_PRIVATE_KEY)


def create_agentkit_wallet():
    """Create a Coinbase wallet via AgentKit. Returns (address, wallet_data) or raises."""
    if not has_cdp_credentials():
        raise RuntimeError(
            "CDP credentials not configured. "
            "Set CDP_API_KEY_NAME and CDP_API_KEY_PRIVATE_KEY environment variables. "
            "Get credentials at https://portal.cdp.coinbase.com"
        )
    try:
        from coinbase_agentkit import AgentKit, AgentKitConfig

        config = AgentKitConfig(
            cdp_api_key_name=CDP_API_KEY_NAME,
            cdp_api_key_private_key=CDP_API_KEY_PRIVATE_KEY,
            network_id="base-mainnet",
        )
        kit = AgentKit(config)
        wallet = kit.wallet
        address = wallet.default_address.address_id
        wallet_data = wallet.export_data()
        return address, wallet_data
    except ImportError:
        raise RuntimeError(
            "coinbase-agentkit not installed. Run: pip install coinbase-agentkit"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to create Coinbase wallet: {e}")
