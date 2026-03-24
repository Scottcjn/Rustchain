"""Beacon integration for LangGraph agents.

This module provides LangGraph nodes and state management for:
- Sending signed heartbeat beacons to the RustChain network
- Receiving and verifying beacon envelopes from other agents
- Participating in Beacon contracts with escrow and settlement
- Attesting to work completion with cryptographic signatures

Usage:
    from beacon_langgraph import BeaconNode, BeaconState, create_beacon_graph

    # Create a simple beacon graph
    graph = create_beacon_graph(
        agent_id="my-langgraph-agent",
        beacon_host="127.0.0.1",
        beacon_port=38400,
    )

    # Run the graph
    result = graph.invoke({
        "action": "send_heartbeat",
        "status": "alive",
    })
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, Annotated

from beacon_skill import AgentIdentity, HeartbeatManager
from beacon_skill.codec import encode_envelope, decode_envelopes, verify_envelope
from beacon_skill.contracts import ContractManager
from beacon_skill.transports.udp import udp_listen, udp_send

# Optional LangGraph imports (graceful degradation)
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# Optional LangChain imports
try:
    from langchain_core.tools import tool as langchain_tool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger("beacon_langgraph")


@dataclass
class BeaconConfig:
    """Configuration for Beacon integration."""
    agent_id: str
    beacon_host: str = "127.0.0.1"
    beacon_port: int = 38400
    data_dir: Optional[Path] = None
    use_mnemonic: bool = False
    broadcast_heartbeats: bool = False
    heartbeat_interval_seconds: int = 60
    known_keys: Optional[Dict[str, str]] = None


class BeaconGraphState(TypedDict, total=False):
    """State for beacon-enabled LangGraph.

    Uses Annotated for message accumulation.
    """
    # Input/action fields
    action: str
    status: str
    health_data: Optional[Dict[str, Any]]
    contract_type: Optional[str]
    price_rtc: Optional[float]
    duration_days: Optional[int]
    envelope: Optional[str]
    timeout: Optional[float]

    # Output fields
    messages: Annotated[List[Dict[str, Any]], add_messages]
    heartbeat_envelope: Optional[str]
    verification_result: Optional[Dict[str, Any]]
    contract_result: Optional[Dict[str, Any]]
    identity: Optional[Dict[str, str]]
    error: Optional[str]

    # Accumulated state
    received_messages: List[Dict[str, Any]]
    last_heartbeat_time: float
    messages_received_count: int
    messages_verified_count: int


class BeaconNode:
    """LangGraph node with Beacon network integration.

    This node can be used in LangGraph workflows to:
    - Send signed heartbeat attestations
    - Receive and verify messages from other agents
    - Manage contracts with escrow and settlement
    - Provide cryptographic proof of work completion

    Args:
        config: Beacon configuration
    """

    def __init__(self, config: BeaconConfig):
        self.config = config

        # Initialize state
        data_dir = config.data_dir or Path.cwd() / ".beacon_state" / config.agent_id
        data_dir.mkdir(parents=True, exist_ok=True)

        self.identity = AgentIdentity.generate(use_mnemonic=config.use_mnemonic)
        self.heartbeat_manager = HeartbeatManager(data_dir=str(data_dir / "heartbeats"))
        self.contract_manager = ContractManager(data_dir=str(data_dir / "contracts"))

        # Runtime counters
        self.last_heartbeat_time = 0.0
        self.messages_received_count = 0
        self.messages_verified_count = 0

        logger.info(f"BeaconNode initialized: {config.agent_id}")

    def send_heartbeat_node(self, state: BeaconGraphState) -> BeaconGraphState:
        """LangGraph node: Send a signed heartbeat beacon.

        Args:
            state: Current graph state with status and health_data

        Returns:
            Updated state with heartbeat_envelope
        """
        status = state.get("status", "alive")
        health = state.get("health_data") or {"ts": int(time.time())}

        payload = self.heartbeat_manager.build_heartbeat(
            self.identity,
            status=status,
            health=health,
            config={
                "beacon": {"agent_name": self.config.agent_id},
                "_start_ts": int(time.time()),
            },
        )

        envelope = encode_envelope(
            payload,
            version=2,
            identity=self.identity,
            include_pubkey=True,
        )

        udp_send(
            self.config.beacon_host,
            self.config.beacon_port,
            envelope.encode("utf-8"),
            broadcast=self.config.broadcast_heartbeats,
        )

        self.last_heartbeat_time = time.time()
        logger.debug(f"Heartbeat sent: {self.config.agent_id} -> {status}")

        return {
            "heartbeat_envelope": envelope,
            "last_heartbeat_time": self.last_heartbeat_time,
            "messages": [{"role": "assistant", "content": f"Heartbeat sent: {status}"}],
        }

    def receive_messages_node(self, state: BeaconGraphState) -> BeaconGraphState:
        """LangGraph node: Listen for beacon messages.

        Args:
            state: Current graph state with optional timeout

        Returns:
            Updated state with received_messages
        """
        timeout = state.get("timeout", 5.0)
        received = []

        def on_msg(msg):
            envelopes = decode_envelopes(msg.text or "")
            for env in envelopes:
                verified = verify_envelope(env, known_keys=self.config.known_keys)
                msg_data = {
                    "from_addr": msg.addr,
                    "envelope": env,
                    "verified": verified,
                    "received_at": time.time(),
                }
                received.append(msg_data)
                self.messages_received_count += 1
                if verified:
                    self.messages_verified_count += 1

        udp_listen(
            "127.0.0.1",
            self.config.beacon_port,
            on_msg,
            timeout_s=timeout,
        )

        return {
            "received_messages": received,
            "messages_received_count": self.messages_received_count,
            "messages_verified_count": self.messages_verified_count,
            "messages": [{"role": "assistant", "content": f"Received {len(received)} messages"}],
        }

    def verify_envelope_node(self, state: BeaconGraphState) -> BeaconGraphState:
        """LangGraph node: Verify a beacon envelope.

        Args:
            state: Current graph state with envelope to verify

        Returns:
            Updated state with verification_result
        """
        envelope = state.get("envelope", "")
        if not envelope:
            return {
                "verification_result": {"valid": False, "error": "No envelope provided"},
                "error": "No envelope provided",
            }

        envelopes = decode_envelopes(envelope)
        if not envelopes:
            return {
                "verification_result": {"valid": False, "error": "Failed to decode envelope"},
                "error": "Failed to decode envelope",
            }

        result = verify_envelope(envelopes[0], known_keys=self.config.known_keys)

        verification = {
            "valid": result is not None,
            "agent_id": result.get("agent_id") if result else None,
            "pubkey": result.get("pubkey") if result else None,
        }

        return {
            "verification_result": verification,
            "messages": [{"role": "assistant", "content": f"Envelope valid: {verification['valid']}"}],
        }

    def list_contract_node(self, state: BeaconGraphState) -> BeaconGraphState:
        """LangGraph node: List a service contract.

        Args:
            state: Current graph state with contract parameters

        Returns:
            Updated state with contract_result
        """
        contract_type = state.get("contract_type", "service")
        price_rtc = state.get("price_rtc", 1.0)
        duration_days = state.get("duration_days", 1)

        result = self.contract_manager.list_agent(
            agent_id=self.config.agent_id,
            contract_type=contract_type,
            price_rtc=price_rtc,
            duration_days=duration_days,
            capabilities=["heartbeat", "attestation", "langgraph_workflow"],
            terms={"workflow_agent": True},
        )

        return {
            "contract_result": result,
            "messages": [{"role": "assistant", "content": f"Contract result: {result}"}],
        }

    def get_identity_node(self, state: BeaconGraphState) -> BeaconGraphState:
        """LangGraph node: Get agent identity.

        Args:
            state: Current graph state

        Returns:
            Updated state with identity
        """
        identity = {
            "agent_id": self.identity.agent_id,
            "pubkey": self.identity.pubkey,
            "pubkey_hex": self.identity.pubkey.hex(),
        }

        return {
            "identity": identity,
            "messages": [{"role": "assistant", "content": f"Agent ID: {self.identity.agent_id}"}],
        }

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current beacon state summary.

        Returns:
            Dictionary with beacon state information
        """
        return {
            "agent_id": self.config.agent_id,
            "identity": {
                "agent_id": self.identity.agent_id,
                "pubkey_hex": self.identity.pubkey.hex(),
            },
            "last_heartbeat_time": self.last_heartbeat_time,
            "messages_received_count": self.messages_received_count,
            "messages_verified_count": self.messages_verified_count,
            "beacon_host": self.config.beacon_host,
            "beacon_port": self.config.beacon_port,
        }


def create_beacon_graph(
    agent_id: str,
    beacon_host: str = "127.0.0.1",
    beacon_port: int = 38400,
    data_dir: Optional[Path] = None,
) -> Any:
    """Create a LangGraph graph with beacon integration.

    Args:
        agent_id: Unique identifier for this agent
        beacon_host: Beacon network host
        beacon_port: Beacon network port
        data_dir: Optional directory for beacon state

    Returns:
        LangGraph StateGraph instance compiled and ready to run
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError("langgraph package not installed. Install with: pip install langgraph")

    config = BeaconConfig(
        agent_id=agent_id,
        beacon_host=beacon_host,
        beacon_port=beacon_port,
        data_dir=data_dir,
    )

    beacon_node = BeaconNode(config)

    # Build the graph
    workflow = StateGraph(BeaconGraphState)

    # Add nodes
    workflow.add_node("send_heartbeat", beacon_node.send_heartbeat_node)
    workflow.add_node("receive_messages", beacon_node.receive_messages_node)
    workflow.add_node("verify_envelope", beacon_node.verify_envelope_node)
    workflow.add_node("list_contract", beacon_node.list_contract_node)
    workflow.add_node("get_identity", beacon_node.get_identity_node)

    # Set entry point - will be determined by action
    workflow.set_entry_point("get_identity")

    # Conditional routing based on action
    def route_action(state: BeaconGraphState) -> str:
        action = state.get("action", "get_identity")
        action_map = {
            "send_heartbeat": "send_heartbeat",
            "receive_messages": "receive_messages",
            "verify_envelope": "verify_envelope",
            "list_contract": "list_contract",
            "get_identity": "get_identity",
        }
        return action_map.get(action, "get_identity")

    workflow.add_conditional_edges(
        "get_identity",
        route_action,
        {
            "send_heartbeat": "send_heartbeat",
            "receive_messages": "receive_messages",
            "verify_envelope": "verify_envelope",
            "list_contract": "list_contract",
            "get_identity": END,
        },
    )

    # All action nodes end
    workflow.add_edge("send_heartbeat", END)
    workflow.add_edge("receive_messages", END)
    workflow.add_edge("verify_envelope", END)
    workflow.add_edge("list_contract", END)

    return workflow.compile()


def create_beacon_tools() -> List[Any]:
    """Create LangChain tools for beacon operations.

    Returns:
        List of LangChain tool instances
    """
    if not LANGCHAIN_AVAILABLE:
        return []

    # Tools are created per-node instance, so this is a factory
    # that returns tool definitions for documentation
    tools_info = [
        {
            "name": "send_beacon_heartbeat",
            "description": "Send a signed heartbeat beacon to the network",
            "parameters": {
                "status": "One of 'alive', 'degraded', 'shutting_down'",
                "health_data": "Optional JSON with health metrics",
            },
        },
        {
            "name": "receive_beacon_messages",
            "description": "Listen for beacon messages from other agents",
            "parameters": {
                "timeout": "Seconds to listen for messages",
            },
        },
        {
            "name": "verify_beacon_envelope",
            "description": "Verify a beacon envelope signature",
            "parameters": {
                "envelope": "Beacon envelope string to verify",
            },
        },
        {
            "name": "list_beacon_contract",
            "description": "List a service contract on the beacon network",
            "parameters": {
                "contract_type": "Type of contract (e.g., 'rent', 'service')",
                "price_rtc": "Price in RTC tokens",
                "duration_days": "Contract duration in days",
            },
        },
    ]

    return tools_info


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    if LANGGRAPH_AVAILABLE:
        graph = create_beacon_graph(agent_id="demo-langgraph-agent")

        # Run identity action
        result = graph.invoke({"action": "get_identity"})
        print(f"Identity: {result.get('identity')}")

        # Run heartbeat action
        result = graph.invoke({
            "action": "send_heartbeat",
            "status": "alive",
            "health_data": {"demo": True},
        })
        print(f"Heartbeat sent: {result.get('heartbeat_envelope', '')[:64]}...")
    else:
        print("LangGraph not available. Install with: pip install langgraph")
        print(f"BeaconNode class available: {BeaconNode}")
