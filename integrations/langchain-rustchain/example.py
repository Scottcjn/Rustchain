#!/usr/bin/env python3
"""Example: Use the RustChain LangChain tools to check a wallet balance
and list open bounties.

Usage:
    pip install langchain-rustchain
    python example.py

This script works with any LangChain-compatible LLM (OpenAI, Anthropic,
Ollama, etc.) or you can just call the tools directly without an LLM.
"""

from langchain_rustchain import (
    RustChainBalanceTool,
    RustChainBountiesTool,
    RustChainCurrentEpochTool,
    RustChainNodeHealthTool,
)


def direct_tool_demo():
    """Demonstrate each tool by calling it directly (no LLM needed)."""

    print("=" * 60)
    print("RustChain LangChain Tools — Direct Demo")
    print("=" * 60)

    # 1. Node health
    print("\n--- 1. Node Health ---")
    health = RustChainNodeHealthTool()._run()
    print(health)

    # 2. Current epoch
    print("\n--- 2. Current Epoch ---")
    epoch = RustChainCurrentEpochTool()._run()
    print(epoch)

    # 3. Wallet balance (any string wallet)
    print("\n--- 3. Wallet Balance (test wallet) ---")
    balance = RustChainBalanceTool()._run("test")
    print(balance)

    # 4. Open bounties
    print("\n--- 4. Open Bounties (top 5) ---")
    bounties = RustChainBountiesTool()._run(limit=5)
    print(bounties)

    print("\n" + "=" * 60)
    print("All tools work. Integrate into your LangChain agent with:")
    print("  from langchain_rustchain import get_tools")
    print("  tools = get_tools()")
    print("=" * 60)


if __name__ == "__main__":
    direct_tool_demo()