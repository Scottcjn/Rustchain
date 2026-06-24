import asyncio
import argparse
import sys
from rustchain_sdk import RustChainClient


async def check_eligibility(miner_id, epoch, node_url, *, insecure_tls=False):
    verify = False if insecure_tls else None
    async with RustChainClient(base_url=node_url, verify=verify) as client:
        try:
            # Use public SDK method
            response = await client.get_epoch_rewards(epoch)
            print(f"Epoch {epoch} Rewards Data:")
            print(response)
            
            # Check balance as well
            balance = await client.get_wallet_balance(miner_id)
            print(f"\nMiner {miner_id} Balance:")
            print(balance)
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RustChain Eligibility Checker")
    parser.add_argument("--miner", required=True, help="Miner ID to check")
    parser.add_argument("--epoch", type=int, required=True, help="Epoch number")
    parser.add_argument("--node", default="https://rustchain.org", help="Node URL (default: https://rustchain.org)")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification for self-signed development nodes.",
    )
    
    args = parser.parse_args()
    asyncio.run(check_eligibility(args.miner, args.epoch, args.node, insecure_tls=args.insecure))
