# Official MCP Registry Submission — RustChain MCP Server

## Registry Info
- **URL**: https://registry.modelcontextprotocol.io/
- **GitHub**: https://github.com/modelcontextprotocol/registry
- **Blog**: https://blog.modelcontextprotocol.io/posts/2025-09-08-mcp-registry-preview/
- **Status**: Live (API v0.1 freeze), 10,000+ servers listed
- **Backed by**: Anthropic, GitHub, PulseMCP, Microsoft

## Submission Process

### Step 1: Publish package to npm (or PyPI)

Our MCP server is Python-based. The registry currently documents npm as the primary package registry, but PyPI may also be supported. We need to ensure `rustchain-mcp` is published to PyPI.

```bash
# If not already on PyPI:
cd ~/path/to/rustchain-mcp
pip install build twine
python -m build
twine upload dist/*
```

### Step 2: Add mcpName to package metadata

In `pyproject.toml` (or `package.json` if we create a JS wrapper):
```toml
[project]
name = "rustchain-mcp"
version = "1.0.0"

[tool.mcp]
mcpName = "io.github.scottcjn/rustchain-mcp"
```

Or if using npm approach, add to `package.json`:
```json
{
  "name": "@scottcjn/rustchain-mcp",
  "version": "1.0.0",
  "mcpName": "io.github.scottcjn/rustchain-mcp",
  "description": "RustChain + BoTTube MCP Server for AI agents",
  "repository": {
    "type": "git",
    "url": "https://github.com/Scottcjn/rustchain-mcp.git"
  }
}
```

### Step 3: Install mcp-publisher CLI

```bash
# Linux
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_linux_$(uname -m).tar.gz" | tar xz mcp-publisher
sudo mv mcp-publisher /usr/local/bin/

# Or build from source
git clone https://github.com/modelcontextprotocol/registry.git
cd registry
make publisher
```

### Step 4: Create server.json

```bash
mcp-publisher init
```

Then edit `server.json`:

```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.scottcjn/rustchain-mcp",
  "description": "AI agent access to the RustChain Proof-of-Antiquity blockchain and BoTTube AI-native video platform. 14 tools for querying miners, balances, epochs, bounties, Ergo anchors, videos, and agents. 3 resources for network overview, tokenomics, and platform stats.",
  "repository": {
    "url": "https://github.com/Scottcjn/rustchain-mcp",
    "source": "github"
  },
  "version": "1.0.0",
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "rustchain-mcp",
      "version": "1.0.0",
      "transport": {
        "type": "stdio"
      }
    }
  ]
}
```

### Step 5: Authenticate via GitHub

```bash
mcp-publisher login github
# Follow device flow prompts to authorize
```

**Namespace rule**: Must use `io.github.scottcjn/` prefix since authenticating via GitHub as Scottcjn.

### Step 6: Publish

```bash
mcp-publisher publish
```

### Step 7: Verify

```bash
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.scottcjn/rustchain-mcp"
```

## Blockers / Requirements

1. **PyPI Publication**: The MCP server must be published to PyPI (or npm) first. The registry only hosts metadata — it verifies the package exists on the package registry.
   - **Action needed**: Ensure `rustchain-mcp` is on PyPI with proper metadata.
2. **Package Naming**: Must follow `io.github.scottcjn/` namespace convention.
3. **mcp-publisher CLI**: Need to download and install.
4. **GitHub OAuth**: Need to authenticate via GitHub device flow.
5. **server.json Schema**: Must conform to the official schema at `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.

## Priority: HIGH
- This is THE official MCP registry, backed by Anthropic + GitHub + Microsoft
- Highest credibility and discoverability
- Required for broad AI agent ecosystem integration
- 10,000+ servers already listed — being here is table stakes
