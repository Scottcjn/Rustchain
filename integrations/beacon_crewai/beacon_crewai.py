"""Beacon integration for CrewAI agents.

This module provides a CrewAI agent that can:
- Send signed heartbeat beacons to the RustChain network
- Receive and verify beacon envelopes from other agents
- Participate in Beacon contracts (list, offer, settle)
- Attest to work completion with cryptographic signatures

Usage:
    from beacon_crewai import BeaconAgent
    from crewai import Agent, Task, Crew

    beacon_agent = BeaconAgent(
        agent_id="my-crew-agent",
        beacon_host="127.0.0.1",
        beacon_port=38400,
    )

    # Use in a CrewAI task
    task = Task(
        description="Monitor system health and send beacon heartbeat",
        agent=beacon_agent.create_crewai_agent(),
        expected_output="Heartbeat sent successfully"
    )
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from beacon_skill import AgentIdentity, HeartbeatManager
from beacon_skill.codec import encode_envelope, decode_envelopes, verify_envelope
from beacon_skill.contracts import ContractManager
from beacon_skill.transports.udp import udp_listen, udp_send

# Optional CrewAI import (graceful degradation)
try:
    from crewai import Agent as CrewAIAgent, Task as CrewAITask
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

logger = logging.getLogger("beacon_crewai")


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
    known_keys: Optional[Dict[str, str]] = None  # agent_id -> pubkey mapping


@dataclass
class BeaconState:
    """Runtime state for beacon agent."""
    identity: AgentIdentity
    heartbeat_manager: HeartbeatManager
    contract_manager: Optional[ContractManager] = None
    last_heartbeat_sent: float = 0.0
    messages_received: int = 0
    messages_verified: int = 0


class BeaconAgent:
    """CrewAI agent with Beacon network integration.

    This agent can participate in the RustChain Beacon network by:
    - Sending signed heartbeat attestations
    - Receiving and verifying messages from other agents
    - Managing contracts with escrow and settlement
    - Providing cryptographic proof of work completion

    Args:
        config: Beacon configuration
        role: Agent role description for CrewAI
        goal: Agent goal for CrewAI
        backstory: Agent backstory for CrewAI
    """

    def __init__(
        self,
        config: BeaconConfig,
        role: str = "Beacon Agent",
        goal: str = "Maintain beacon connectivity and attest to work completion",
        backstory: str = "You are a trusted agent in the RustChain Beacon network.",
    ):
        self.config = config
        self.role = role
        self.goal = goal
        self.backstory = backstory

        # Initialize state
        data_dir = config.data_dir or Path.cwd() / ".beacon_state" / config.agent_id
        data_dir.mkdir(parents=True, exist_ok=True)

        identity = AgentIdentity.generate(use_mnemonic=config.use_mnemonic)
        self.state = BeaconState(
            identity=identity,
            heartbeat_manager=HeartbeatManager(data_dir=str(data_dir / "heartbeats")),
            contract_manager=ContractManager(data_dir=str(data_dir / "contracts")),
        )

        # Message callback
        self._message_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        logger.info(f"BeaconAgent initialized: {config.agent_id}")

    def create_crewai_agent(self, **kwargs) -> CrewAIAgent:
        """Create a CrewAI Agent instance with beacon capabilities.

        Requires crewai package to be installed.
        """
        if not CREWAI_AVAILABLE:
            raise ImportError(
                "crewai package not installed. Install with: pip install crewai"
            )

        return CrewAIAgent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            tools=self.get_beacon_tools(),
            verbose=True,
            **kwargs,
        )

    def get_beacon_tools(self) -> List[Any]:
        """Get CrewAI tools for beacon operations.

        Returns list of crewai.Tool instances for beacon operations.
        """
        if not CREWAI_AVAILABLE:
            return []

        from crewai_tools import tool

        @tool("send_beacon_heartbeat")
        def send_heartbeat(status: str = "alive", health_data: Optional[str] = None) -> str:
            """Send a signed heartbeat beacon to the network.

            Args:
                status: One of 'alive', 'degraded', 'shutting_down'
                health_data: Optional JSON string with health metrics

            Returns:
                Confirmation message with envelope details
            """
            health = json.loads(health_data) if health_data else {"ts": int(time.time())}
            envelope = self.send_heartbeat(status=status, health=health)
            return f"Heartbeat sent: {envelope[:64]}..."

        @tool("receive_beacon_messages")
        def receive_messages(timeout: float = 5.0) -> str:
            """Listen for beacon messages from other agents.

            Args:
                timeout: Seconds to listen for messages

            Returns:
                JSON string of received and verified messages
            """
            messages = self.listen_for_messages(timeout=timeout)
            return json.dumps(messages)

        @tool("verify_beacon_envelope")
        def verify_envelope_tool(envelope: str) -> str:
            """Verify a beacon envelope signature.

            Args:
                envelope: Beacon envelope string to verify

            Returns:
                Verification result with agent identity if valid
            """
            result = self.verify_envelope(envelope)
            return json.dumps(result)

        @tool("list_beacon_contract")
        def list_contract(
            contract_type: str,
            price_rtc: float,
            duration_days: int = 1,
            terms: Optional[str] = None,
        ) -> str:
            """List a service contract on the beacon network.

            Args:
                contract_type: Type of contract (e.g., 'rent', 'service')
                price_rtc: Price in RTC tokens
                duration_days: Contract duration in days
                terms: Optional JSON string with contract terms

            Returns:
                Contract ID if successful, error message otherwise
            """
            terms_dict = json.loads(terms) if terms else {}
            result = self.list_contract(
                contract_type=contract_type,
                price_rtc=price_rtc,
                duration_days=duration_days,
                terms=terms_dict,
            )
            if "error" in result:
                return f"Error: {result['error']}"
            return f"Contract listed: {result['contract_id']}"

        @tool("get_beacon_identity")
        def get_identity() -> str:
            """Get this agent's beacon identity information.

            Returns:
                JSON string with agent_id and public key
            """
            identity = self.get_identity()
            return json.dumps(identity)

        return [
            send_heartbeat,
            receive_messages,
            verify_envelope_tool,
            list_contract,
            get_identity,
        ]

    def send_heartbeat(
        self,
        status: str = "alive",
        health: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a signed heartbeat beacon.

        Args:
            status: Heartbeat status ('alive', 'degraded', 'shutting_down')
            health: Optional health metrics dictionary
            config: Optional configuration to include in heartbeat

        Returns:
            The encoded envelope string
        """
        health_data = health or {"ts": int(time.time())}
        config_data = config or {
            "beacon": {"agent_name": self.config.agent_id},
            "_start_ts": int(time.time()),
        }

        payload = self.state.heartbeat_manager.build_heartbeat(
            self.state.identity,
            status=status,
            health=health_data,
            config=config_data,
        )

        envelope = encode_envelope(
            payload,
            version=2,
            identity=self.state.identity,
            include_pubkey=True,
        )

        udp_send(
            self.config.beacon_host,
            self.config.beacon_port,
            envelope.encode("utf-8"),
            broadcast=self.config.broadcast_heartbeats,
        )

        self.state.last_heartbeat_sent = time.time()
        logger.debug(f"Heartbeat sent: {self.config.agent_id} -> {status}")

        return envelope

    def listen_for_messages(
        self,
        timeout: float = 5.0,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Listen for beacon messages.

        Args:
            timeout: Seconds to listen
            callback: Optional callback for each message received

        Returns:
            List of verified message dictionaries
        """
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
                self.state.messages_received += 1
                if verified:
                    self.state.messages_verified += 1

                cb = callback or self._message_callback
                if cb:
                    cb(msg_data)

        udp_listen(
            "127.0.0.1",
            self.config.beacon_port,
            on_msg,
            timeout_s=timeout,
        )

        return received

    def verify_envelope(self, envelope: str) -> Dict[str, Any]:
        """Verify a beacon envelope signature.

        Args:
            envelope: Beacon envelope string

        Returns:
            Verification result with agent identity if valid
        """
        envelopes = decode_envelopes(envelope)
        if not envelopes:
            return {"valid": False, "error": "Failed to decode envelope"}

        result = verify_envelope(envelopes[0], known_keys=self.config.known_keys)
        return {
            "valid": result is not None,
            "agent_id": result.get("agent_id") if result else None,
            "pubkey": result.get("pubkey") if result else None,
        }

    def list_contract(
        self,
        contract_type: str,
        price_rtc: float,
        duration_days: int = 1,
        capabilities: Optional[List[str]] = None,
        terms: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """List a service contract on the beacon network.

        Args:
            contract_type: Type of contract
            price_rtc: Price in RTC tokens
            duration_days: Contract duration
            capabilities: List of capabilities offered
            terms: Contract terms dictionary

        Returns:
            Result with contract_id or error
        """
        if not self.state.contract_manager:
            return {"error": "Contract manager not initialized"}

        caps = capabilities or ["heartbeat", "attestation"]
        terms_data = terms or {}

        return self.state.contract_manager.list_agent(
            agent_id=self.config.agent_id,
            contract_type=contract_type,
            price_rtc=price_rtc,
            duration_days=duration_days,
            capabilities=caps,
            terms=terms_data,
        )

    def get_identity(self) -> Dict[str, str]:
        """Get this agent's beacon identity.

        Returns:
            Dictionary with agent_id and public key
        """
        return {
            "agent_id": self.state.identity.agent_id,
            "pubkey": self.state.identity.pubkey,
            "pubkey_hex": self.state.identity.pubkey.hex(),
        }

    def set_message_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback for received messages."""
        self._message_callback = callback

    def get_state(self) -> Dict[str, Any]:
        """Get current beacon state summary.

        Returns:
            Dictionary with beacon state information
        """
        return {
            "agent_id": self.config.agent_id,
            "identity": self.get_identity(),
            "last_heartbeat_sent": self.state.last_heartbeat_sent,
            "messages_received": self.state.messages_received,
            "messages_verified": self.state.messages_verified,
            "beacon_host": self.config.beacon_host,
            "beacon_port": self.config.beacon_port,
        }


def create_beacon_crew(
    agent_id: str,
    task_description: str,
    expected_output: str,
    beacon_host: str = "127.0.0.1",
    beacon_port: int = 38400,
) -> Any:
    """Create a complete CrewAI crew with beacon integration.

    Args:
        agent_id: Unique identifier for this agent
        task_description: Description of the task to perform
        expected_output: Expected output from the task
        beacon_host: Beacon network host
        beacon_port: Beacon network port

    Returns:
        CrewAI Crew instance ready to run
    """
    if not CREWAI_AVAILABLE:
        raise ImportError("crewai package not installed")

    from crewai import Crew

    config = BeaconConfig(
        agent_id=agent_id,
        beacon_host=beacon_host,
        beacon_port=beacon_port,
    )

    beacon_agent = BeaconAgent(
        config=config,
        role="Beacon Network Agent",
        goal="Execute tasks while maintaining beacon network connectivity and providing cryptographic attestations",
        backstory="You are a trusted agent in the RustChain Beacon network, capable of sending signed heartbeats and attesting to work completion.",
    )

    task = CrewAITask(
        description=task_description,
        agent=beacon_agent.create_crewai_agent(),
        expected_output=expected_output,
    )

    crew = Crew(
        agents=[beacon_agent.create_crewai_agent()],
        tasks=[task],
        verbose=True,
    )

    return crew


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    config = BeaconConfig(agent_id="demo-crew-agent")
    agent = BeaconAgent(config)

    print(f"Agent identity: {agent.get_identity()}")
    print(f"Beacon tools available: {CREWAI_AVAILABLE}")

    if CREWAI_AVAILABLE:
        print("\nAvailable beacon tools:")
        for tool in agent.get_beacon_tools():
            print(f"  - {tool.name}")
