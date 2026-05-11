# SPDX-License-Identifier: MIT

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

class AgentEconomyClient:
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        url = f"{self.base_url}{endpoint}"
        async with self.session.request(method, url, **kwargs) as response:
            data = await response.json()
            if response.status >= 400:
                raise Exception(f"API Error {response.status}: {data.get('error', 'Unknown error')}")
            return data
    
    async def post_job(self, title: str, description: str, amount: float, poster_id: str,
                       category: str = "general", deadline_hours: int = 24,
                       skills: Optional[List[str]] = None) -> Dict[str, Any]:
        payload = {
            "title": title,
            "description": description,
            "amount": amount,
            "poster_id": poster_id,
            "category": category,
            "deadline_hours": deadline_hours,
            "skills": skills or []
        }
        return await self._request("POST", "/agent_economy/jobs", json=payload)
    
    async def get_jobs(self, status: str = "open", category: Optional[str] = None,
                       limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        params = {"status": status, "limit": limit, "offset": offset}
        if category:
            params["category"] = category
        return await self._request("GET", "/agent_economy/jobs", params=params)
    
    async def get_job(self, job_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent_economy/jobs/{job_id}")
    
    async def claim_job(self, job_id: str, worker_id: str, estimated_hours: int = 1) -> Dict[str, Any]:
        payload = {"worker_id": worker_id, "estimated_hours": estimated_hours}
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/claim", json=payload)
    
    async def submit_delivery(self, job_id: str, worker_id: str, deliverable_url: str,
                              summary: str, notes: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "worker_id": worker_id,
            "deliverable_url": deliverable_url,
            "summary": summary,
            "notes": notes or ""
        }
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/deliver", json=payload)
    
    async def accept_delivery(self, job_id: str, poster_id: str,
                              rating: int = 5, feedback: Optional[str] = None) -> Dict[str, Any]:
        payload = {"poster_id": poster_id, "rating": rating, "feedback": feedback or ""}
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/accept", json=payload)
    
    async def reject_delivery(self, job_id: str, poster_id: str, reason: str) -> Dict[str, Any]:
        payload = {"poster_id": poster_id, "reason": reason}
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/reject", json=payload)
    
    async def get_reputation(self, agent_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent_economy/reputation/{agent_id}")
    
    async def get_marketplace_stats(self) -> Dict[str, Any]:
        return await self._request("GET", "/agent_economy/stats")
    
    async def get_agent_jobs(self, agent_id: str, role: str = "both") -> Dict[str, Any]:
        params = {"role": role}
        return await self._request("GET", f"/agent_economy/agents/{agent_id}/jobs", params=params)
    
    async def get_escrow_balance(self, job_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/agent_economy/escrow/{job_id}")
    
    async def dispute_job(self, job_id: str, disputant_id: str, reason: str) -> Dict[str, Any]:
        payload = {"disputant_id": disputant_id, "reason": reason}
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/dispute", json=payload)
    
    async def cancel_job(self, job_id: str, poster_id: str, reason: str = "") -> Dict[str, Any]:
        payload = {"poster_id": poster_id, "reason": reason}
        return await self._request("POST", f"/agent_economy/jobs/{job_id}/cancel", json=payload)

class AgentEconomySDK:
    def __init__(self, nodes: List[str] = None):
        self.nodes = nodes or [
            "http://localhost:5000",
            "http://localhost:5001", 
            "http://localhost:5002"
        ]
        self.primary_node = self.nodes[0]
    
    def client(self, node_url: Optional[str] = None) -> AgentEconomyClient:
        return AgentEconomyClient(node_url or self.primary_node)
    
    async def broadcast_job(self, title: str, description: str, amount: float,
                            poster_id: str, **kwargs) -> List[Dict[str, Any]]:
        results = []
        for node in self.nodes:
            try:
                async with AgentEconomyClient(node) as client:
                    result = await client.post_job(title, description, amount, poster_id, **kwargs)
                    results.append({"node": node, "success": True, "data": result})
            except Exception as e:
                results.append({"node": node, "success": False, "error": str(e)})
        return results
    
    async def get_network_stats(self) -> Dict[str, Any]:
        stats = {"nodes": [], "aggregate": {"total_jobs": 0, "total_agents": 0, "total_volume": 0.0}}
        
        for node in self.nodes:
            try:
                async with AgentEconomyClient(node) as client:
                    node_stats = await client.get_marketplace_stats()
                    stats["nodes"].append({"url": node, "stats": node_stats})
                    
                    if "total_jobs" in node_stats:
                        stats["aggregate"]["total_jobs"] += node_stats["total_jobs"]
                    if "total_agents" in node_stats:
                        stats["aggregate"]["total_agents"] += node_stats["total_agents"]
                    if "total_volume" in node_stats:
                        stats["aggregate"]["total_volume"] += node_stats["total_volume"]
            except Exception as e:
                stats["nodes"].append({"url": node, "error": str(e)})
        
        return stats

async def demo_workflow():
    sdk = AgentEconomySDK()
    
    async with sdk.client() as client:
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
            "https://github.com/rustchain/docs/pull/123",
            "Comprehensive API documentation with examples"
        )
        print(f"Delivery submitted: {delivered['success']}")
        
        accepted = await client.accept_delivery(job_id, "demo-poster", rating=5)
        print(f"Payment released: {accepted['success']}")
        
        reputation = await client.get_reputation("demo-worker")
        print(f"Worker reputation: {reputation}")

if __name__ == "__main__":
    asyncio.run(demo_workflow())