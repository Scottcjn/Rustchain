# RustChain MCP - Usage Guide

Detailed usage examples and integration patterns for the RustChain MCP server.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Python Client API](#python-client-api)
3. [MCP Client Configuration](#mcp-client-configuration)
4. [Error Handling](#error-handling)
5. [Best Practices](#best-practices)

---

## Basic Usage

### Health Check

```python
from rustchain_mcp import get_health

async def check_status():
    health = await get_health()
    print(f"Status: {health.status}")
    print(f"Healthy: {health.is_healthy}")
    print(f"Version: {health.version}")
    print(f"Uptime: {health.uptime_s}s")
```

### Get Epoch Info

```python
from rustchain_mcp import get_epoch

async def get_current_epoch():
    epoch = await get_epoch()
    print(f"Epoch: {epoch.epoch}")
    print(f"Slot: {epoch.slot}")
    print(f"Height: {epoch.height}")

async def get_specific_epoch():
    epoch = await get_epoch(epoch_number=90)
    print(f"Epoch 90: {epoch}")
```

### Check Balance

```python
from rustchain_mcp import get_balance

async def check_wallet():
    balance = await get_balance("scott")
    print(f"Miner: {balance.miner_id}")
    print(f"Balance: {balance.amount_rtc} RTC")
    print(f"Balance (i64): {balance.amount_i64}")
    print(f"Total (with staked): {balance.total_rtc} RTC")
```

### Execute Query

```python
from rustchain_mcp import run_query

async def query_miners():
    result = await run_query("miners", limit=10)
    if result.success:
        print(f"Found {result.count} miners")
        print(f"Data: {result.data}")
    else:
        print(f"Error: {result.error}")
```

---

## Python Client API

### Using RustChainClient Class

```python
from rustchain_mcp import RustChainClient

async def main():
    async with RustChainClient() as client:
        # Health check
        health = await client.health()
        
        # Epoch info
        epoch = await client.epoch()
        
        # Balance
        balance = await client.balance("scott")
        
        # Network stats
        stats = await client.stats()
        
        # Miners list
        miners = await client.miners(limit=10)
        
        # Custom query
        result = await client.query("blocks", params={"from": 100})
```

### Custom Configuration

```python
from rustchain_mcp import RustChainClient

client = RustChainClient(
    base_url="https://50.28.86.131",
    timeout=60,        # 60 second timeout
    retry_count=3,     # Retry 3 times on failure
)
```

### Manual Session Management

```python
from rustchain_mcp import RustChainClient
import aiohttp

async def main():
    # Create your own session
    session = aiohttp.ClientSession()
    
    try:
        client = RustChainClient(session=session)
        await client._ensure_session()
        
        # Use client...
        health = await client.health()
    finally:
        await client.close()
        await session.close()
```

---

## MCP Client Configuration

### Claude Desktop

Create or edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rustchain": {
      "command": "python",
      "args": ["-m", "rustchain_mcp.mcp_server"],
      "env": {
        "RUSTCHAIN_API_BASE": "https://50.28.86.131",
        "RUSTCHAIN_TIMEOUT": "30"
      }
    }
  }
}
```

### Cursor

Create `.cursor/mcp.json` in your project:

```json
{
  "rustchain": {
    "command": "python",
    "args": ["-m", "rustchain_mcp.mcp_server"],
    "cwd": "/path/to/RustChain/integrations/rustchain-mcp"
  }
}
```

### Windsurf

Add to Windsurf MCP settings:

```json
{
  "name": "rustchain",
  "command": "python",
  "args": ["-m", "rustchain_mcp.mcp_server"],
  "env": {
    "RUSTCHAIN_API_BASE": "https://50.28.86.131"
  }
}
```

---

## Error Handling

### API Errors

```python
from rustchain_mcp import RustChainClient, APIError

async def safe_balance_check(miner_id):
    async with RustChainClient() as client:
        try:
            balance = await client.balance(miner_id)
            return balance.amount_rtc
        except APIError as e:
            if e.status_code == 404:
                print(f"Miner {miner_id} not found")
            elif e.status_code >= 500:
                print(f"Server error: {e.message}")
            else:
                print(f"API error: {e.code} - {e.message}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
```

### Connection Errors

```python
from rustchain_mcp import RustChainClient
import aiohttp

async def check_connectivity():
    async with RustChainClient() as client:
        try:
            is_alive = await client.ping()
            if is_alive:
                print("API is reachable")
            else:
                print("API is not reachable")
        except aiohttp.ClientError as e:
            print(f"Connection error: {e}")
```

### Retry Logic

```python
from rustchain_mcp import RustChainClient
import asyncio

async def query_with_retry(query_type, max_retries=3):
    async with RustChainClient(retry_count=max_retries) as client:
        try:
            return await client.query(query_type)
        except APIError as e:
            if e.status_code == 429:  # Rate limited
                await asyncio.sleep(1)
                return await client.query(query_type)
            raise
```

---

## Best Practices

### 1. Reuse Client Instances

```python
# ❌ Bad: Creating new client for each request
async def get_data():
    async with RustChainClient() as c1:
        health = await c1.health()
    async with RustChainClient() as c2:
        epoch = await c2.epoch()

# ✅ Good: Reuse same client
async def get_data():
    async with RustChainClient() as client:
        health = await client.health()
        epoch = await client.epoch()
```

### 2. Handle Missing Data

```python
async def get_balance_safe(miner_id):
    async with RustChainClient() as client:
        try:
            balance = await client.balance(miner_id)
            return {
                "found": True,
                "balance": balance.amount_rtc,
            }
        except APIError as e:
            if e.status_code == 404:
                return {"found": False, "error": "Miner not found"}
            raise
```

### 3. Use Appropriate Timeouts

```python
# For quick health checks
quick_client = RustChainClient(timeout=5)

# For large queries
query_client = RustChainClient(timeout=60)
```

### 4. Batch Related Queries

```python
async def get_miner_summary(miner_ids):
    async with RustChainClient() as client:
        results = []
        for miner_id in miner_ids:
            try:
                balance = await client.balance(miner_id)
                results.append({
                    "miner_id": miner_id,
                    "balance": balance.amount_rtc,
                })
            except APIError:
                results.append({
                    "miner_id": miner_id,
                    "error": "Not found",
                })
        return results
```

### 5. Cache Frequently Accessed Data

```python
import asyncio

class CachedRustChainClient:
    def __init__(self, client, cache_ttl=60):
        self.client = client
        self.cache_ttl = cache_ttl
        self._cache = {}
        self._timestamps = {}
    
    async def epoch(self):
        if self._is_valid("epoch"):
            return self._cache["epoch"]
        
        epoch = await self.client.epoch()
        self._cache["epoch"] = epoch
        self._timestamps["epoch"] = asyncio.get_event_loop().time()
        return epoch
    
    def _is_valid(self, key):
        if key not in self._cache:
            return False
        age = asyncio.get_event_loop().time() - self._timestamps[key]
        return age < self.cache_ttl
```

---

## Integration Examples

### Discord Bot Integration

```python
import discord
from rustchain_mcp import RustChainClient

client = discord.Client(intents=discord.Intents.default())
rustchain = RustChainClient()

@client.event
async def on_ready():
    await rustchain._ensure_session()
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.content.startswith("!balance"):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("Usage: !balance <miner_id>")
            return
        
        miner_id = parts[1]
        try:
            balance = await rustchain.balance(miner_id)
            await message.channel.send(
                f"{miner_id}: {balance.amount_rtc} RTC"
            )
        except Exception as e:
            await message.channel.send(f"Error: {e}")

client.run("DISCORD_TOKEN")
```

### Web API Endpoint

```python
from fastapi import FastAPI
from rustchain_mcp import RustChainClient

app = FastAPI()
rustchain = RustChainClient()

@app.on_event("startup")
async def startup():
    await rustchain._ensure_session()

@app.get("/health")
async def health():
    h = await rustchain.health()
    return {"healthy": h.is_healthy, "version": h.version}

@app.get("/balance/{miner_id}")
async def balance(miner_id: str):
    b = await rustchain.balance(miner_id)
    return {"miner_id": b.miner_id, "balance_rtc": b.amount_rtc}

@app.get("/epoch")
async def epoch():
    e = await rustchain.epoch()
    return {"epoch": e.epoch, "slot": e.slot}
```

### CLI Tool

```python
#!/usr/bin/env python3
import asyncio
import sys
from rustchain_mcp import RustChainClient

async def main():
    if len(sys.argv) < 2:
        print("Usage: rustchain-cli <command> [args]")
        print("Commands: health, epoch, balance <miner_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    async with RustChainClient() as client:
        if command == "health":
            h = await client.health()
            print(f"Status: {h.status}")
            print(f"Version: {h.version}")
        elif command == "epoch":
            e = await client.epoch()
            print(f"Epoch: {e.epoch}")
            print(f"Slot: {e.slot}")
        elif command == "balance":
            if len(sys.argv) < 3:
                print("Error: miner_id required")
                sys.exit(1)
            b = await client.balance(sys.argv[2])
            print(f"Balance: {b.amount_rtc} RTC")
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### Connection Refused

```
Error: Connection refused
```

**Solution:** Check that the RustChain API is accessible:
```bash
curl -sk https://50.28.86.131/api/health
```

### SSL Certificate Error

```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solution:** The client disables SSL verification by default. If you need to verify:
```python
import ssl
import aiohttp

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))
client = RustChainClient(session=session)
```

### Rate Limiting

```
API error: 429 Too Many Requests
```

**Solution:** Implement exponential backoff:
```python
import asyncio

async def query_with_backoff(client, query_type):
    for attempt in range(5):
        try:
            return await client.query(query_type)
        except APIError as e:
            if e.status_code == 429:
                wait = 2 ** attempt
                await asyncio.sleep(wait)
            else:
                raise
```

---

<div align="center">

**RustChain MCP Server** | [Documentation](README.md) | [API Reference](../../../docs/api-reference.md)

</div>
