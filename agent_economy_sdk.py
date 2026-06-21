import asyncio
import json

class AgentEconomySDK:
    # ... (other methods) ...

    async def trigger_payout(self, miner_id, wallet_address):
        try:
            # Logic to trigger payout for the miner's rewards
            payout_amount = await self.get_accumulated_rewards(miner_id)
            if payout_amount > 0:
                response = await self.client.post_payout(miner_id, wallet_address, payout_amount)
                return response
            else:
                return {"success": False, "error": "No rewards to payout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_accumulated_rewards(self, miner_id):
        # Logic to fetch accumulated rewards for the miner
        # This is a placeholder implementation
        return 15.0  # Example fixed value for testing

async def demo_workflow():
    sdk = AgentEconomySDK()
    miner_id = "nkar123412-hub"
    wallet_address = "RTC6ac6e74adbb358fd8d8fd54abe79c97439c05f28"
    async with sdk.client() as client:
        # Trigger payout for the miner
        payout_response = await sdk.trigger_payout(miner_id, wallet_address)
        print(f"Payout triggered: {payout_response['success']}")

        job = await client.post_job(
            title="Write RustChain documentation",
            description="Create comprehensive API docs for the agent economy",
            amount=15.75,
            poster_id="demo-poster",
            category="writing",
            deadline_hours=48,
            skills=["technical-writing", "blockchain", "api-docs"]
        )
        job_id = job["job"]["job_id"]
        print(f"Created job: {job_id}")
        claimed = await client.claim_job(job_id, "demo-worker", estimated_hours=8)
        print(f"Job claimed: {claimed['success']}")
        delivered = await client.submit_delivery(
            job_id, "demo-worker",
            "https://github.com/Scottcjn/Rustchain/pull/123",
            "Comprehensive API documentation with examples"
        )
        print(f"Delivery submitted: {delivered['success']}")
        accepted = await client.accept_delivery(job_id, "demo-poster", rating=5)
        print(f"Payment released: {accepted['success']}")
        reputation = await client.get_reputation("demo-worker")
        print(f"Worker reputation: {reputation}")

if __name__ == "__main__":
    asyncio.run(demo_workflow())