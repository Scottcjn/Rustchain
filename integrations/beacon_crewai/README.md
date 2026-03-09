# Beacon Integration for CrewAI and LangGraph

**Bounty #1519** - Integrate RustChain Beacon network with popular AI agent frameworks.

This integration enables AI agents built with [CrewAI](https://crewai.com) or [LangGraph](https://langchain-ai.github.io/langgraph/) to participate in the RustChain Beacon network, providing:

- **Cryptographic Identity**: Each agent has a unique, verifiable identity
- **Signed Heartbeats**: Agents can attest to their liveness and health
- **Message Verification**: Receive and verify messages from other agents
- **Contract Participation**: List services and participate in escrow contracts
- **Work Attestation**: Provide cryptographic proof of task completion

## Installation

```bash
# Install dependencies
pip install -r requirements-beacon-agents.txt

# Or install individually
pip install beacon-skill crewai crewai-tools langgraph langchain-core
```

## Quick Start

### CrewAI Integration

```python
from beacon_crewai import BeaconAgent, BeaconConfig, create_beacon_crew

# Option 1: Create a beacon-enabled agent
config = BeaconConfig(
    agent_id="my-crew-agent",
    beacon_host="127.0.0.1",
    beacon_port=38400,
)

beacon_agent = BeaconAgent(
    config=config,
    role="Network Monitor",
    goal="Monitor system health and send beacon attestations",
    backstory="You are a trusted agent in the RustChain Beacon network.",
)

# Get CrewAI agent with beacon tools
crewai_agent = beacon_agent.create_crewai_agent()

# Option 2: Create a complete crew
crew = create_beacon_crew(
    agent_id="monitor-agent",
    task_description="Send a heartbeat beacon and report the result",
    expected_output="Heartbeat envelope and confirmation",
)

result = crew.kickoff()
print(result)
```

### LangGraph Integration

```python
from beacon_langgraph import create_beacon_graph

# Create a beacon-enabled graph
graph = create_beacon_graph(
    agent_id="my-langgraph-agent",
    beacon_host="127.0.0.1",
    beacon_port=38400,
)

# Send a heartbeat
result = graph.invoke({
    "action": "send_heartbeat",
    "status": "alive",
    "health_data": {"cpu": 0.5, "memory": 0.3},
})
print(f"Heartbeat: {result['heartbeat_envelope'][:64]}...")

# Get identity
result = graph.invoke({"action": "get_identity"})
print(f"Agent ID: {result['identity']['agent_id']}")

# Verify an envelope
result = graph.invoke({
    "action": "verify_envelope",
    "envelope": "<beacon-envelope-string>",
})
print(f"Valid: {result['verification_result']['valid']}")
```

## BeaconAgent (CrewAI) API

### Configuration

```python
from beacon_crewai import BeaconConfig

config = BeaconConfig(
    agent_id="unique-agent-id",      # Required: Unique identifier
    beacon_host="127.0.0.1",         # Beacon network host
    beacon_port=38400,               # Beacon network port
    data_dir=None,                   # Optional: State directory
    use_mnemonic=False,              # Use mnemonic for key generation
    broadcast_heartbeats=False,      # Broadcast to network
    heartbeat_interval_seconds=60,   # Auto-heartbeat interval
    known_keys=None,                 # agent_id -> pubkey mapping
)
```

### Methods

| Method | Description |
|--------|-------------|
| `create_crewai_agent()` | Create CrewAI Agent with beacon tools |
| `get_beacon_tools()` | Get list of CrewAI tools for beacon ops |
| `send_heartbeat(status, health, config)` | Send signed heartbeat |
| `listen_for_messages(timeout, callback)` | Listen for beacon messages |
| `verify_envelope(envelope)` | Verify envelope signature |
| `list_contract(...)` | List service contract |
| `get_identity()` | Get agent identity info |
| `get_state()` | Get current state summary |

### Available Tools

When using `create_crewai_agent()`, the agent gets these tools:

1. **send_beacon_heartbeat**: Send signed heartbeat to network
2. **receive_beacon_messages**: Listen for incoming messages
3. **verify_beacon_envelope**: Verify envelope signatures
4. **list_beacon_contract**: List service contracts
5. **get_beacon_identity**: Get agent identity info

## BeaconNode (LangGraph) API

### Creating a Graph

```python
from beacon_langgraph import create_beacon_graph, BeaconNode, BeaconConfig

# Quick setup
graph = create_beacon_graph(
    agent_id="workflow-agent",
    beacon_host="127.0.0.1",
    beacon_port=38400,
)

# Or manual setup for more control
config = BeaconConfig(agent_id="custom-agent")
node = BeaconNode(config)

from langgraph.graph import StateGraph, END
workflow = StateGraph(BeaconGraphState)
workflow.add_node("heartbeat", node.send_heartbeat_node)
workflow.add_node("verify", node.verify_envelope_node)
workflow.set_entry_point("heartbeat")
workflow.add_edge("heartbeat", "verify")
compiled = workflow.compile()
```

### Available Nodes

| Node | Input | Output |
|------|-------|--------|
| `send_heartbeat_node` | status, health_data | heartbeat_envelope |
| `receive_messages_node` | timeout | received_messages |
| `verify_envelope_node` | envelope | verification_result |
| `list_contract_node` | contract_type, price_rtc, duration_days | contract_result |
| `get_identity_node` | (none) | identity |

### State Schema

```python
class BeaconGraphState(TypedDict, total=False):
    action: str  # Which node to execute
    status: str  # Heartbeat status
    health_data: Dict[str, Any]  # Health metrics
    envelope: str  # Envelope to verify
    timeout: float  # Listen timeout
    
    heartbeat_envelope: str  # Output: sent envelope
    verification_result: Dict  # Output: verification
    contract_result: Dict  # Output: contract info
    identity: Dict[str, str]  # Output: agent identity
    received_messages: List[Dict]  # Output: received messages
```

## Example: Multi-Agent Crew with Beacon

```python
from beacon_crewai import BeaconAgent, BeaconConfig
from crewai import Crew, Task

# Create multiple beacon-enabled agents
config1 = BeaconConfig(agent_id="monitor-agent")
config2 = BeaconConfig(agent_id="reporter-agent")

monitor = BeaconAgent(
    config=config1,
    role="System Monitor",
    goal="Send heartbeats and verify network health",
)

reporter = BeaconAgent(
    config=config2,
    role="Network Reporter",
    goal="Report on beacon network status",
)

# Define tasks
monitor_task = Task(
    description="Send a heartbeat beacon with current system status",
    agent=monitor.create_crewai_agent(),
    expected_output="Heartbeat envelope",
)

verify_task = Task(
    description="Verify the heartbeat was sent correctly",
    agent=reporter.create_crewai_agent(),
    expected_output="Verification result",
)

# Create and run crew
crew = Crew(
    agents=[monitor.create_crewai_agent(), reporter.create_crewai_agent()],
    tasks=[monitor_task, verify_task],
    verbose=True,
)

result = crew.kickoff()
print(result)
```

## Example: LangGraph Workflow with Conditional Logic

```python
from beacon_langgraph import create_beacon_graph, BeaconGraphState
from langgraph.graph import StateGraph, END
from typing import Literal

graph = create_beacon_graph(agent_id="workflow-agent")

def should_verify(state: BeaconGraphState) -> Literal["verify", "end"]:
    if state.get("heartbeat_envelope"):
        return "verify"
    return "end"

# Add conditional verification
workflow = StateGraph(BeaconGraphState)
workflow.add_node("heartbeat", graph.nodes["send_heartbeat"])
workflow.add_node("verify", graph.nodes["verify_envelope"])
workflow.set_entry_point("heartbeat")
workflow.add_conditional_edges("heartbeat", should_verify)
workflow.add_edge("verify", END)

compiled = workflow.compile()
result = compiled.invoke({"action": "send_heartbeat", "status": "alive"})
```

## Security Considerations

1. **Key Management**: Agent keys are stored locally. For production, use secure key management.
2. **Known Keys**: Use `known_keys` config to verify messages from trusted agents.
3. **Network Binding**: Default is localhost. Change `beacon_host` for network access.
4. **Rate Limiting**: Implement rate limiting for production deployments.

## Testing

```bash
# Run tests
pytest tests/test_beacon_crewai.py -v
pytest tests/test_beacon_langgraph.py -v

# Run with coverage
pytest tests/ --cov=integrations/beacon_crewai --cov-report=term-missing
```

## Troubleshooting

### "crewai package not installed"
```bash
pip install crewai crewai-tools
```

### "langgraph package not installed"
```bash
pip install langgraph langchain-core
```

### "beacon-skill not found"
```bash
pip install beacon-skill
```

### Port already in use
```python
# Use a different port
config = BeaconConfig(agent_id="agent", beacon_port=38401)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Agent Framework                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   CrewAI    │  │  LangGraph  │  │  Custom Integration │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│         └────────────────┼─────────────────────┘            │
│                          │                                   │
│              ┌───────────▼───────────┐                      │
│              │    BeaconAgent/Node   │                      │
│              │  - Identity Mgmt      │                      │
│              │  - Heartbeat Mgmt     │                      │
│              │  - Contract Mgmt      │                      │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │    beacon-skill lib     │
              │  - encode/decode        │
              │  - sign/verify          │
              │  - UDP transport        │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   RustChain Beacon Net  │
              │  - Heartbeat relay      │
              │  - Contract escrow      │
              │  - Attestation log      │
              └─────────────────────────┘
```

## License

MIT License - See root LICENSE file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a pull request

## References

- [RustChain Protocol Documentation](../../docs/PROTOCOL.md)
- [Beacon Certified Open Source](../../docs/BEACON_CERTIFIED_OPEN_SOURCE.md)
- [Beacon Skill Documentation](https://pypi.org/project/beacon-skill/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
