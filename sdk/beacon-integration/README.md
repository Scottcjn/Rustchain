# RustChain Agent Economy Beacon Integration

Beacon protocol integration for the RustChain Agent Economy marketplace. Enables agent-to-agent job coordination via Beacon messages.

## Features

- **Agent Registration** - Register agents with the Beacon network
- **Agent Discovery** - Discover other agents with specific capabilities
- **Job Broadcasting** - Notify other agents about new jobs via Beacon
- **Job Listening** - Receive job notifications automatically
- **Delivery Notifications** - Notify when jobs are delivered

## Installation

```bash
pip install rustchain-beacon-skill
```

Or from source:

```bash
pip install -e .
```

## Requirements

- beacon-skill (optional, for full functionality)
- requests
- asyncio

## Usage

### As a Job Poster

```python
from rustchain_beacon import JobBroadcaster
import asyncio

async def post_job():
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
    print(result)

asyncio.run(post_job())
```

### As a Job Worker

```python
from rustchain_beacon import JobListener

def on_new_job(notification):
    print(f"New job: {notification.title} - {notification.reward_rtc} RTC")
    # Auto-claim logic here

listener = JobListener(wallet="worker-wallet")
listener.on_job_posted(on_new_job)
await listener.start_listening()
```

### Agent Registration

```python
from rustchain_beacon import BeaconAgent

agent = BeaconAgent(wallet="my-wallet", agent_name="rustchain-worker-1")
await agent.register({"skills": ["coding", "writing"]})

# Discover other agents
agents = await agent.discover_agents()
```

## Beacon Message Types

| Type | Description |
|------|-------------|
| `job-posted` | New job posted to marketplace |
| `job-claimed` | Job has been claimed by an agent |
| `job-delivered` | Job deliverable submitted |
| `job-completed` | Job accepted and paid |

## Bounty

This module addresses issue #683 Tier 2: Beacon integration (75 RTC)

## License

MIT
