"""Beacon integration for CrewAI and LangGraph agent frameworks.

This package provides integration between the RustChain Beacon network
and popular AI agent frameworks, enabling:

- Cryptographic identity for AI agents
- Signed heartbeat attestations
- Message verification from other agents
- Contract participation with escrow
- Work completion attestations

Modules:
    beacon_crewai: CrewAI agent integration
    beacon_langgraph: LangGraph node integration
"""

try:
    from .beacon_crewai import (
        BeaconAgent,
        BeaconConfig,
        CREWAI_AVAILABLE,
        create_beacon_crew,
    )
    from .beacon_langgraph import (
        BeaconNode,
        BeaconConfig as LangGraphBeaconConfig,
        BeaconGraphState,
        LANGCHAIN_AVAILABLE,
        LANGGRAPH_AVAILABLE,
        create_beacon_graph,
        create_beacon_tools,
    )
except ImportError:
    from beacon_crewai import (
        BeaconAgent,
        BeaconConfig,
        CREWAI_AVAILABLE,
        create_beacon_crew,
    )
    from beacon_langgraph import (
        BeaconNode,
        BeaconConfig as LangGraphBeaconConfig,
        BeaconGraphState,
        LANGCHAIN_AVAILABLE,
        LANGGRAPH_AVAILABLE,
        create_beacon_graph,
        create_beacon_tools,
    )

__version__ = "0.1.0"
__all__ = [
    # CrewAI
    "BeaconAgent",
    "BeaconConfig",
    "create_beacon_crew",
    "CREWAI_AVAILABLE",
    # LangGraph
    "BeaconNode",
    "LangGraphBeaconConfig",
    "BeaconGraphState",
    "create_beacon_graph",
    "create_beacon_tools",
    "LANGCHAIN_AVAILABLE",
    "LANGGRAPH_AVAILABLE",
]
