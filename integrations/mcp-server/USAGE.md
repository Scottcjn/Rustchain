# RustChain MCP Server - Example Usage

This directory contains example usage of the RustChain MCP Server with various AI assistants.

## Claude Desktop

1. Install the MCP server:
```bash
cd integrations/mcp-server
pip install -e .
```

2. Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["/absolute/path/to/RustChain/integrations/mcp-server/mcp_server.py"]
    }
  }
}
```

3. Restart Claude Desktop

4. Ask questions like:
   - "What's the current RustChain network status?"
   - "Show me active miners with PowerPC hardware"
   - "How much would I earn mining on a PowerBook G4 for a week?"
   - "What open bounties are worth more than 50 RTC?"

## Cursor IDE

1. Create `.cursor/mcp.json` in your project:
```json
{
  "rustchain": {
    "command": "python",
    "args": ["/absolute/path/to/RustChain/integrations/mcp-server/mcp_server.py"]
  }
}
```

2. Cursor will automatically connect to the MCP server

3. Use in chat:
   - "Check the balance of wallet XYZ"
   - "Find bounties related to blockchain bridges"
   - "Verify if my Power Mac G5 is eligible for mining"

## Programmatic Usage

```python
import asyncio
import aiohttp
from mcp_server import RustChainMCP

async def main():
    server = RustChainMCP()
    await server.start()
    
    # Get network stats
    stats = await server._tool_get_network_stats()
    print(f"Current epoch: {stats.get('current_epoch')}")
    
    # Get active miners
    miners = await server._tool_get_active_miners({"limit": 10})
    print(f"Active miners: {miners['count']}")
    
    # Verify hardware
    hw_check = await server._tool_verify_hardware({
        "cpu_model": "PowerPC G4",
        "architecture": "PowerPC",
        "is_vm": False
    })
    print(f"Multiplier: {hw_check['multiplier']}x")
    
    await server.stop()

asyncio.run(main())
```

## Testing with MCP Inspector

The MCP Inspector is a debugging tool for MCP servers:

```bash
# Install
npx @modelcontextprotocol/inspector

# Run with your server
npx @modelcontextprotocol/inspector python mcp_server.py
```

This opens a web UI where you can:
- Test tool calls
- Read resources
- Try prompts
- Debug issues

## Example Conversations

### Mining Rewards Calculation

**User:** I have a PowerBook G4 1.5GHz. How much would I earn if I mine for 30 days?

**AI:** Let me calculate that for you using the RustChain mining rewards tool.

*[AI calls `calculate_mining_rewards` with:]*
```json
{
  "hardware_type": "PowerPC G4",
  "epochs": 4320,
  "uptime_percent": 90
}
```

**AI:** Based on your PowerPC G4 hardware:
- **Hardware multiplier:** 2.5x (150% bonus!)
- **Epochs in 30 days:** 4,320
- **Estimated rewards:** 972 RTC (~$97.20)
- **Breakdown:**
  - Base rewards: 388.8 RTC
  - Hardware bonus: 583.2 RTC

Your vintage hardware earns significantly more than modern systems!

### Bounty Discovery

**User:** What are the best open bounties right now?

**AI:** Let me fetch the open bounties for you.

*[AI calls `get_bounty_info` with `min_reward=50`]*

**AI:** Here are the high-value open bounties (50+ RTC):

1. **Ergo Mainnet Bridge** - 150 RTC
   - Issue #23
   - Anchor RustChain state to Ergo

2. **TradingView Chart Widget** - 60 RTC
   - Issue #26
   - Build embeddable price chart

3. **7-Day Mining Bounty** - 15 RTC (pool: 500 RTC)
   - Issue #166
   - Mine for 7 days on real hardware

Would you like more details on any of these?

### Hardware Compatibility

**User:** Can I mine on my 2015 MacBook Pro?

**AI:** Let me check your hardware compatibility.

*[AI calls `verify_hardware` with:]*
```json
{
  "cpu_model": "Intel Core i7",
  "architecture": "x86_64",
  "is_vm": false
}
```

**AI:** Yes! Your 2015 MacBook Pro is eligible:
- **Hardware type:** Modern x86
- **Multiplier:** 1.0x (base rate)
- **Status:** ✅ Eligible for mining

While it doesn't get the vintage bonus, it's still a perfectly valid miner. You'd earn standard rewards based on your uptime.

---

For more examples, see the main [README.md](README.md).
