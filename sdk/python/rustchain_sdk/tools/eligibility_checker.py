import asyncio
import argparse
import sys
from rustchain_sdk import RustChainClient

async def check_eligibility(miner_id, epoch, node_url):
    async with RustChainClient(base_url=node_url, verify=False) as client:
        try:
            # Check if there's an endpoint for this in the actual API
            # Based on the SDK, we might have to use generic _get if not explicitly implemented
            response = await client._get("/epoch/rewards", params={"epoch_number": epoch})
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
    parser.add_argument("--node", default="https://50.28.86.131", help="Node URL")
    
    args = parser.parse_args()
    asyncio.run(check_eligibility(args.miner, args.epoch, args.node))
