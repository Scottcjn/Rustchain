"""
RustChain Agent Economy Beacon Integration

This module provides Beacon protocol integration for the RustChain
Agent Economy marketplace. It allows agents to:

1. Register with the Beacon network
2. Discover other agents
3. Post job notifications via Beacon
4. Receive job notifications from other agents
5. Coordinate job delivery via Beacon messages

Usage:
    from rustchain_beacon import BeaconAgent, JobBroadcaster, JobListener
    
    # As a job poster
    broadcaster = JobBroadcaster(wallet="my-wallet")
    await broadcaster.post_job_notification(job_id, title, reward)
    
    # As a job listener
    listener = JobListener(wallet="my-wallet")
    await listener.start_listening()
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from datetime import datetime

# Try to import beacon-skill, fallback to mock if not available
try:
    from beacon import BeaconClient
    BEACON_AVAILABLE = True
except ImportError:
    BEACON_AVAILABLE = False


@dataclass
class JobNotification:
    """Job notification payload for Beacon messages."""
    job_id: str
    title: str
    category: str
    reward_rtc: float
    poster_wallet: str
    description: str
    timestamp: str


class BeaconAgent:
    """
    Base class for Beacon-enabled Agent Economy agents.
    Handles agent registration and discovery.
    """
    
    def __init__(self, wallet: str, agent_name: str = None, base_url: str = "https://rustchain.org/beacon/api"):
        self.wallet = wallet
        self.agent_name = agent_name or wallet
        self.base_url = base_url
        self.beacon_client = None
        
        if BEACON_AVAILABLE:
            try:
                self.beacon_client = BeaconClient(base_url=base_url)
            except Exception as e:
                print(f"Failed to initialize Beacon client: {e}")
    
    async def register(self, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Register this agent with the Beacon network."""
        if not self.beacon_client:
            return {"success": False, "error": "Beacon client not available"}
        
        agent_metadata = {
            "wallet": self.wallet,
            "agent_name": self.agent_name,
            "type": "agent-economy",
            "capabilities": ["job-posting", "job-working", "job-delivery"],
            **(metadata or {})
        }
        
        try:
            # Register with Beacon
            result = await self.beacon_client.register(
                agent_id=self.agent_name,
                metadata=agent_metadata
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def discover_agents(self, capability: str = None) -> List[Dict[str, Any]]:
        """Discover other agents in the Beacon network."""
        if not self.beacon_client:
            return []
        
        try:
            agents = await self.beacon_client.discover(
                filter_type="agent-economy" if not capability else capability
            )
            return agents
        except Exception as e:
            print(f"Error discovering agents: {e}")
            return []
    
    async def send_message(self, target_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to another agent via Beacon."""
        if not self.beacon_client:
            return {"success": False, "error": "Beacon client not available"}
        
        try:
            result = await self.beacon_client.send(
                to=target_agent,
                message=json.dumps(message),
                message_type="agent-economy"
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


class JobBroadcaster:
    """
    Broadcasts job postings to the Beacon network.
    Uses Beacon to notify other agents about new jobs.
    """
    
    def __init__(self, wallet: str, base_url: str = "https://rustchain.org/beacon/api"):
        self.wallet = wallet
        self.base_url = base_url
        self.beacon_client = None
        
        if BEACON_AVAILABLE:
            try:
                self.beacon_client = BeaconClient(base_url=base_url)
            except Exception as e:
                print(f"Failed to initialize Beacon client: {e}")
    
    async def post_job_notification(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Broadcast a job posting to the Beacon network.
        
        Args:
            job: Job details including job_id, title, category, reward_rtc, poster_wallet, description
        """
        notification = JobNotification(
            job_id=job.get("id") or job.get("job_id"),
            title=job.get("title"),
            category=job.get("category"),
            reward_rtc=job.get("reward_rtc"),
            poster_wallet=job.get("poster_wallet"),
            description=job.get("description"),
            timestamp=datetime.utcnow().isoformat()
        )
        
        message = {
            "type": "job-posted",
            "payload": {
                "job_id": notification.job_id,
                "title": notification.title,
                "category": notification.category,
                "reward_rtc": notification.reward_rtc,
                "poster_wallet": notification.poster_wallet,
                "description": notification.description[:200],  # Truncate for Beacon
                "timestamp": notification.timestamp
            }
        }
        
        if not self.beacon_client:
            # Return mock success for testing
            return {
                "success": True, 
                "mock": True,
                "notification": message,
                "message": "Beacon client not available, notification mocked"
            }
        
        try:
            # Broadcast to all agent-economy capable agents
            result = await self.beacon_client.broadcast(
                message=json.dumps(message),
                message_type="job-posted",
                filter_type="agent-economy"
            )
            return {"success": True, "result": result, "notification": message}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def notify_job_claimed(self, job_id: str, worker_wallet: str) -> Dict[str, Any]:
        """Notify that a job has been claimed."""
        message = {
            "type": "job-claimed",
            "payload": {
                "job_id": job_id,
                "worker_wallet": worker_wallet,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        if not self.beacon_client:
            return {"success": True, "mock": True, "message": message}
        
        try:
            result = await self.beacon_client.broadcast(
                message=json.dumps(message),
                message_type="job-claimed"
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def notify_job_delivered(self, job_id: str, worker_wallet: str, deliverable_url: str) -> Dict[str, Any]:
        """Notify that a job has been delivered."""
        message = {
            "type": "job-delivered",
            "payload": {
                "job_id": job_id,
                "worker_wallet": worker_wallet,
                "deliverable_url": deliverable_url,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        if not self.beacon_client:
            return {"success": True, "mock": True, "message": message}
        
        try:
            result = await self.beacon_client.broadcast(
                message=json.dumps(message),
                message_type="job-delivered"
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


class JobListener:
    """
    Listens for job postings from the Beacon network.
    Allows agents to automatically discover and react to new jobs.
    """
    
    def __init__(self, wallet: str, base_url: str = "https://rustchain.org/beacon/api"):
        self.wallet = wallet
        self.base_url = base_url
        self.beacon_client = None
        self.running = False
        self.callbacks: List[Callable] = []
        
        if BEACON_AVAILABLE:
            try:
                self.beacon_client = BeaconClient(base_url=base_url)
            except Exception as e:
                print(f"Failed to initialize Beacon client: {e}")
    
    def on_job_posted(self, callback: Callable[[JobNotification], None]):
        """Register a callback for job posted events."""
        self.callbacks.append(callback)
    
    async def start_listening(self):
        """Start listening for job notifications."""
        self.running = True
        
        if not self.beacon_client:
            print("Beacon client not available, running in mock mode")
            return
        
        try:
            await self.beacon_client.subscribe(
                message_type="job-posted",
                callback=self._handle_message
            )
        except Exception as e:
            print(f"Error starting listener: {e}")
    
    async def stop_listening(self):
        """Stop listening for job notifications."""
        self.running = False
        
        if self.beacon_client:
            try:
                await self.beacon_client.unsubscribe("job-posted")
            except Exception as e:
                print(f"Error stopping listener: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming Beacon messages."""
        try:
            data = json.loads(message.get("data", "{}"))
            
            if data.get("type") == "job-posted":
                payload = data.get("payload", {})
                notification = JobNotification(
                    job_id=payload.get("job_id"),
                    title=payload.get("title"),
                    category=payload.get("category"),
                    reward_rtc=payload.get("reward_rtc"),
                    poster_wallet=payload.get("poster_wallet"),
                    description=payload.get("description"),
                    timestamp=payload.get("timestamp")
                )
                
                # Notify callbacks
                for callback in self.callbacks:
                    try:
                        callback(notification)
                    except Exception as e:
                        print(f"Error in callback: {e}")
        
        except Exception as e:
            print(f"Error handling message: {e}")


# Example Usage
async def main():
    """Example demonstrating Beacon integration."""
    
    # Example 1: Register an agent
    agent = BeaconAgent(wallet="my-wallet", agent_name="rustchain-worker-1")
    result = await agent.register({"skills": ["coding", "writing"]})
    print("Agent registration:", result)
    
    # Example 2: Discover other agents
    agents = await agent.discover_agents()
    print(f"Discovered {len(agents)} agents")
    
    # Example 3: Broadcast a job
    broadcaster = JobBroadcaster(wallet="my-wallet")
    job = {
        "id": "job_123",
        "title": "Write a blog post",
        "category": "writing",
        "reward_rtc": 5.0,
        "poster_wallet": "my-wallet",
        "description": "Write about RustChain"
    }
    result = await broadcaster.post_job_notification(job)
    print("Job notification:", result)
    
    # Example 4: Listen for jobs
    listener = JobListener(wallet="my-wallet")
    
    def on_new_job(notification: JobNotification):
        print(f"New job: {notification.title} - {notification.reward_rtc} RTC")
    
    listener.on_job_posted(on_new_job)
    await listener.start_listening()
    
    # Keep running
    await asyncio.sleep(10)
    await listener.stop_listening()


if __name__ == "__main__":
    asyncio.run(main())
