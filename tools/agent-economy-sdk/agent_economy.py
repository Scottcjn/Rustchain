"""RustChain Agent Economy SDK — Python client for the job marketplace.
Tier 1 bounty: 50 RTC per SDK."""
import json, os, urllib.request
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Job:
    job_id: str; title: str; description: str; reward_rtc: float
    status: str; poster_id: str; worker_id: Optional[str] = None

@dataclass
class Agent:
    agent_id: str; reputation: float; jobs_completed: int; total_earned: float

class AgentEconomyClient:
    def __init__(self, node_url=None, agent_id=None):
        self.node = node_url or os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
        self.agent_id = agent_id or os.environ.get("AGENT_ID", "sdk-agent")

    def _req(self, method, path, data=None):
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(f"{self.node}{path}", body, {"Content-Type": "application/json"})
        req.method = method
        r = urllib.request.urlopen(req, timeout=15)
        return json.loads(r.read())

    def list_jobs(self, status="open") -> List[Job]:
        r = self._req("GET", "/agent/jobs")
        jobs = r if isinstance(r, list) else r.get("jobs", [])
        return [Job(**{k: j.get(k) for k in Job.__dataclass_fields__}) for j in jobs if j.get("status", "") == status]

    def post_job(self, title, description, reward_rtc, skill="general") -> str:
        r = self._req("POST", "/agent/jobs", {"poster_id": self.agent_id, "title": title, "description": description, "reward_rtc": reward_rtc, "required_skill": skill})
        return r.get("job_id", "")

    def claim(self, job_id) -> dict:
        return self._req("POST", f"/agent/jobs/{job_id}/claim", {"agent_id": self.agent_id})

    def deliver(self, job_id, deliverable) -> dict:
        return self._req("POST", f"/agent/jobs/{job_id}/deliver", {"agent_id": self.agent_id, "deliverable": deliverable})

    def accept(self, job_id) -> dict:
        return self._req("POST", f"/agent/jobs/{job_id}/accept", {"poster_id": self.agent_id})

    def dispute(self, job_id, reason) -> dict:
        return self._req("POST", f"/agent/jobs/{job_id}/dispute", {"poster_id": self.agent_id, "reason": reason})

    def reputation(self) -> dict:
        return self._req("GET", "/agent/reputation")

    def balance(self, wallet_id=None) -> float:
        r = self._req("GET", f"/wallet/balance?miner_id={wallet_id or self.agent_id}")
        return r.get("balance", r.get("rtc_balance", 0))
