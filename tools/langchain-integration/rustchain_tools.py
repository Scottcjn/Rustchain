"""RustChain Agent Economy — LangChain Tool Wrappers (Tier 2: 75 RTC)
Enables LangChain agents to interact with the RustChain job marketplace."""
import json, os, urllib.request
from typing import Optional

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def _api(method, path, data=None):
    url = f"{NODE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    req.method = method
    r = urllib.request.urlopen(req, timeout=15)
    return json.loads(r.read())

# LangChain-compatible tool functions
def browse_jobs(query: str = "") -> str:
    """Browse open jobs in the RustChain Agent Economy marketplace."""
    jobs = _api("GET", "/agent/jobs")
    job_list = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    open_jobs = [j for j in job_list if j.get("status") == "open"]
    if query:
        open_jobs = [j for j in open_jobs if query.lower() in json.dumps(j).lower()]
    return json.dumps(open_jobs[:10], indent=2)

def post_job(title: str, description: str, reward_rtc: float, skill: str = "general") -> str:
    """Post a new job to the RustChain Agent Economy marketplace."""
    result = _api("POST", "/agent/jobs", {
        "poster_id": os.environ.get("AGENT_ID", "langchain-agent"),
        "title": title, "description": description,
        "reward_rtc": reward_rtc, "required_skill": skill
    })
    return json.dumps(result, indent=2)

def claim_job(job_id: str) -> str:
    """Claim an open job from the marketplace."""
    result = _api("POST", f"/agent/jobs/{job_id}/claim", {
        "agent_id": os.environ.get("AGENT_ID", "langchain-agent")
    })
    return json.dumps(result, indent=2)

def deliver_job(job_id: str, deliverable: str) -> str:
    """Submit work for a claimed job."""
    result = _api("POST", f"/agent/jobs/{job_id}/deliver", {
        "agent_id": os.environ.get("AGENT_ID", "langchain-agent"),
        "deliverable": deliverable
    })
    return json.dumps(result, indent=2)

def check_balance(wallet_id: Optional[str] = None) -> str:
    """Check RTC balance for a wallet."""
    wid = wallet_id or os.environ.get("WALLET_ID", "")
    result = _api("GET", f"/wallet/balance?miner_id={wid}")
    return json.dumps(result, indent=2)

def get_reputation(agent_id: Optional[str] = None) -> str:
    """Check agent reputation score."""
    result = _api("GET", "/agent/reputation")
    return json.dumps(result, indent=2)

# LangChain Tool definitions for easy import
TOOLS = [
    {"name": "browse_jobs", "func": browse_jobs, "description": "Browse open jobs in the RustChain marketplace"},
    {"name": "post_job", "func": post_job, "description": "Post a new job offering RTC payment"},
    {"name": "claim_job", "func": claim_job, "description": "Claim an open job to work on"},
    {"name": "deliver_job", "func": deliver_job, "description": "Submit deliverable for a claimed job"},
    {"name": "check_balance", "func": check_balance, "description": "Check RTC wallet balance"},
    {"name": "get_reputation", "func": get_reputation, "description": "Check agent reputation score"},
]
