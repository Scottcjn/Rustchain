#!/usr/bin/env python3
"""Test MCP Server functionality."""

import ast
import sys
import os

# Parse the mcp_server.py file to verify tools
def test_tools_defined():
    """Test that all required tools are defined in the source code."""
    filepath = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Required bounty tools
    required = [
        "rustchain_health",
        "rustchain_balance",
        "rustchain_miners",
        "rustchain_epoch",
        "rustchain_create_wallet",
        "rustchain_submit_attestation",
        "rustchain_bounties",
    ]
    
    # Check tool definitions
    print("=== Tool Definitions ===")
    for tool in required:
        if f'name="{tool}"' in content or f"name='{tool}'" in content:
            print(f"✅ {tool} defined")
        else:
            print(f"❌ {tool} MISSING!")
    
    # Check tool handlers
    print("\n=== Tool Handlers ===")
    for tool in required:
        handler = f"_tool_{tool}"
        if f"async def {handler}" in content:
            print(f"✅ {handler}")
        else:
            print(f"❌ {handler} MISSING!")
    
    # Count total tools
    total_tools = content.count('name="') + content.count("name='")
    print(f"\nTotal tool definitions: {total_tools}")
    
    # Check syntax
    print("\n=== Syntax Check ===")
    try:
        ast.parse(content)
        print("✅ Python syntax valid")
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False
    
    return all(f"async def _tool_{tool}" in content for tool in required)


def main():
    """Run tests."""
    print("Testing MCP Server...\n")
    
    try:
        success = test_tools_defined()
        
        if success:
            print("\n✅ All required bounty tools are present!")
        else:
            print("\n❌ Some required tools are missing!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
