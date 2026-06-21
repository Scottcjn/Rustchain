async def demo_workflow():
    sdk = AgentEconomySDK()
    
    async with sdk.client() as client:
        # First check and process any pending epoch settlements
        await client.process_epoch_settlements(miner_id='nkar123412-hub')
        
        job = await client.post_job(
            title="Write RustChain documentation",
            description="Create comprehensive API docs for the agent economy",
            amount=15.75,
            poster_id="demo-poster",
            category="writing",
            deadline_hours=48,
            skills=["technical-writing", "blockchain", "api-docs"]
        )