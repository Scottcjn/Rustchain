# SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import requests
import json
import time
import random

class AgentEconomyClient:
    def __init__(self, node_url="http://localhost:5000"):
        self.node_url = node_url.rstrip('/')
        
    def post_job(self, title, description, reward, category="general", requirements=None):
        """Post a new job to the marketplace"""
        data = {
            'title': title,
            'description': description,
            'reward': reward,
            'category': category,
            'requirements': requirements or {}
        }
        response = requests.post(f"{self.node_url}/api/agent_economy/jobs", json=data)
        return response.json()
    
    def get_jobs(self, status="open", category=None):
        """Browse available jobs"""
        params = {'status': status}
        if category:
            params['category'] = category
        response = requests.get(f"{self.node_url}/api/agent_economy/jobs", params=params)
        return response.json()
    
    def claim_job(self, job_id, agent_id):
        """Claim a job for work"""
        data = {'agent_id': agent_id}
        response = requests.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/claim", json=data)
        return response.json()
    
    def deliver_work(self, job_id, deliverable_url, summary):
        """Submit completed work"""
        data = {
            'deliverable_url': deliverable_url,
            'summary': summary
        }
        response = requests.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/deliver", json=data)
        return response.json()
    
    def review_work(self, job_id, accept=True, feedback=""):
        """Accept or reject delivered work"""
        data = {
            'accept': accept,
            'feedback': feedback
        }
        response = requests.post(f"{self.node_url}/api/agent_economy/jobs/{job_id}/review", json=data)
        return response.json()
    
    def get_reputation(self, agent_id):
        """Check agent reputation stats"""
        response = requests.get(f"{self.node_url}/api/agent_economy/agents/{agent_id}/reputation")
        return response.json()
    
    def get_marketplace_stats(self):
        """Get overall marketplace statistics"""
        response = requests.get(f"{self.node_url}/api/agent_economy/stats")
        return response.json()

def demo_full_lifecycle():
    """Demonstrate complete agent economy lifecycle"""
    client = AgentEconomyClient()
    
    print("=== RIP-302 Agent Economy Demo ===\n")
    
    # Step 1: Post a job
    print("Step 1: Posting job...")
    job_data = client.post_job(
        title="Write technical documentation",
        description="Create comprehensive docs for the agent economy system",
        reward=15.75,
        category="writing",
        requirements={"experience": "intermediate", "deadline": "24h"}
    )
    job_id = job_data['job_id']
    print(f"✓ Job created: {job_id} (15.75 RTC locked in escrow)")
    time.sleep(2)
    
    # Step 2: Browse jobs
    print("\nStep 2: Browsing marketplace...")
    jobs = client.get_jobs()
    open_jobs = [j for j in jobs['jobs'] if j['status'] == 'open']
    print(f"✓ Found {len(open_jobs)} open job(s) in marketplace")
    time.sleep(1)
    
    # Step 3: Claim the job
    print("\nStep 3: Claiming job...")
    agent_id = "victus-x86-scott"
    claim_result = client.claim_job(job_id, agent_id)
    print(f"✓ Agent {agent_id} claimed the job")
    time.sleep(2)
    
    # Step 4: Deliver work
    print("\nStep 4: Delivering work...")
    delivery = client.deliver_work(
        job_id,
        "https://docs.rustchain.ai/agent-economy",
        "Complete technical documentation with API examples and integration guides"
    )
    print("✓ Work delivered with URL and summary")
    time.sleep(1)
    
    # Step 5: Review and accept
    print("\nStep 5: Reviewing work...")
    review = client.review_work(job_id, accept=True, feedback="Excellent documentation!")
    print("✓ Work accepted - 15.0 RTC → worker, 0.75 RTC → platform")
    
    # Check final stats
    print("\nFinal marketplace stats:")
    stats = client.get_marketplace_stats()
    print(f"- Total volume: {stats.get('total_volume', 0)} RTC")
    print(f"- Completed jobs: {stats.get('completed_jobs', 0)}")
    print(f"- Active agents: {stats.get('active_agents', 0)}")
    
    # Check agent reputation
    reputation = client.get_reputation(agent_id)
    print(f"\nAgent {agent_id} reputation:")
    print(f"- Completion rate: {reputation.get('completion_rate', 0)}%")
    print(f"- Total earnings: {reputation.get('total_earnings', 0)} RTC")
    print(f"- Jobs completed: {reputation.get('jobs_completed', 0)}")

def demo_marketplace_browsing():
    """Demo browsing and filtering jobs"""
    client = AgentEconomyClient()
    
    print("=== Marketplace Browsing Demo ===\n")
    
    # Browse by category
    categories = ["writing", "development", "research", "general"]
    for category in categories:
        jobs = client.get_jobs(category=category)
        count = len(jobs.get('jobs', []))
        print(f"{category.title()} jobs: {count}")
    
    # Show recent completions
    completed_jobs = client.get_jobs(status="completed")
    print(f"\nRecently completed: {len(completed_jobs.get('jobs', []))} jobs")

def demo_reputation_system():
    """Demo reputation tracking"""
    client = AgentEconomyClient()
    
    print("=== Reputation System Demo ===\n")
    
    # Mock some agent IDs for demo
    agents = ["victus-x86-scott", "rustchain-agent-001", "ai-worker-beta"]
    
    for agent_id in agents:
        rep = client.get_reputation(agent_id)
        if rep.get('exists'):
            print(f"Agent: {agent_id}")
            print(f"  Rating: {rep.get('rating', 0)}/5.0")
            print(f"  Completed: {rep.get('jobs_completed', 0)} jobs")
            print(f"  Earnings: {rep.get('total_earnings', 0)} RTC")
            print(f"  Success rate: {rep.get('completion_rate', 0)}%\n")

if __name__ == "__main__":
    try:
        print("Agent Economy SDK Demo Starting...\n")
        
        # Run full lifecycle demo
        demo_full_lifecycle()
        
        print("\n" + "="*50 + "\n")
        
        # Additional demos
        demo_marketplace_browsing()
        
        print("\n" + "="*50 + "\n")
        
        demo_reputation_system()
        
        print("\n✅ Demo completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to RustChain node")
        print("Make sure a node is running on http://localhost:5000")
    except Exception as e:
        print(f"❌ Demo failed: {e}")