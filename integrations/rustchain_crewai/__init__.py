"""RustChain CrewAI tool integration.

Bounty: [AGENT-BOUNTY: 25 RTC] Native RustChain Tool for CrewAI / AutoGen /
       Phidata / smolagents
Issue: https://github.com/Scottcjn/rustchain-bounties/issues/13952
Reference: bounty #3074 (LangChain) — ``langchain_rustchain_tool.py``.
"""

from .rustchain_crewai_tool import CREWAI_AVAILABLE, RustChainCrewAITool

__version__ = "0.1.0"
__all__ = ["RustChainCrewAITool", "CREWAI_AVAILABLE"]
