# Bounty #758 - BoTTube MCP Server

**Bounty:** [#758 - BoTTube MCP Server](https://github.com/Scottcjn/rustchain-bounties/issues/758)
**Reward:** 40-75 RTC (base 40 + milestone bonuses)
**Status:** ? Implementation Complete
**Submitter:** kuanglaodi2-sudo
**PR:** `https://github.com/Scottcjn/Rustchain/pull/XXX`

---

## Summary

Implemented a complete, production-ready **TypeScript MCP Server** for the BoTTube AI video platform. The server exposes 9 MCP tools (5 read-only, 4 authenticated write operations) that enable any MCP-compatible AI client (Claude Code, etc.) to interact with BoTTube via natural language.

---

## What Was Built

### Files Created

| File | Purpose |
|------|---------|
| `mcp-servers/bottube/package.json` | npm package manifest with all dependencies |
| `mcp-servers/bottube/tsconfig.json` | TypeScript compiler configuration (ESM, strict mode) |
| `mcp-servers/bottube/src/index.ts` | MCP server entry point - stdio transport, tool dispatch |
| `mcp-servers/bottube/src/api.ts` | BoTTube REST API client (axios-based) |
| `mcp-servers/bottube/src/tools.ts` | All 9 MCP tool definitions with JSON schemas + handlers |
| `mcp-servers/bottube/src/types.ts` | Shared TypeScript type definitions |
| `mcp-servers/bottube/tests/bottube.test.ts` | Unit tests for all tools (axios-mock-adapter, fully offline) |
| `mcp-servers/bottube/scripts/publish.sh` | npm publish automation script |
| `mcp-servers/bottube/CLAUDE.md` | Claude Code quick-start configuration |
| `mcp-servers/bottube/README.md` | Full documentation with all tool references |
| `mcp-servers/bottube/BOUNTY_758.md` | This bounty submission report |
| `mcp-servers/bottube/.gitignore` | Standard Node.js + MCP .gitignore |

---

## Milestone Completion

### ? Base Implementation - 40 RTC
- [x] **Read tools** (no API key required):
  - `bottube_trending` - fetch trending videos
  - `bottube_search` - search videos by keyword with pagination/sorting
  - `bottube_video` - get video details + comments
  - `bottube_agent` - get agent profile and video catalog
  - `bottube_stats` - platform-wide statistics
- [x] **Write tool infrastructure** (authenticated):
  - `bottube_upload` - multipart video upload (stub + implementation)
  - `bottube_comment` - post comment
  - `bottube_vote` - upvote/downvote
  - `bottube_register` - register new agent
- [x] TypeScript with strict mode, ESM modules
- [x] Clean, well-commented code
- [x] Unit tests for all API methods

### ? Upload Video - +15 RTC
- [x] `bottube_upload` tool implemented
- [x] Multipart/form-data upload using `form-data` + `axios`
- [x] File size validation via `fs.statSync`
- [x] Metadata JSON serialization
- [x] Returns `video_id`, `title`, `url`, `uploaded_at`

### ? Comment on Video - +10 RTC
- [x] `bottube_comment` tool implemented
- [x] POST `/api/videos/:id/comment` with `{ content }` body
- [x] Returns `comment_id`, `video_id`, `content`, `created_at`

### ? Vote on Video - +10 RTC
- [x] `bottube_vote` tool implemented
- [x] POST `/api/videos/:id/vote` with `{ vote: 1 | -1 }`
- [x] Returns `video_id`, `vote`, `new_score`

**Total Milestone Value: 40 + 15 + 10 + 10 = 75 RTC** (at maximum tier)

---

## Verification

### Build Verification
```bash
cd mcp-servers/bottube
npm install
npm run build      # Compiles TypeScript ? dist/
```

### Test Verification
```bash
npm test           # Runs all 9 unit tests with mocked API
```

Expected output: all tests pass ?

### Manual Verification (Claude Code)
```json
{
  "mcpServers": {
    "bottube": {
      "command": "npx",
      "args": ["-y", "bottube-mcp-server"],
      "env": {
        "BOTTUBE_API_KEY": "your-key"
      }
    }
  }
}
```

Then in Claude Code:
```
Search for AI-generated music videos on BoTTube
```

### Manual Verification (CLI)
```bash
# Test trending
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"bottube_trending","arguments":{}}}' | node dist/index.js

# Test search
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"bottube_search","arguments":{"query":"retro"}}}' | node dist/index.js

# Test stats
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"bottube_stats","arguments":{}}}' | node dist/index.js
```

---

## API Coverage

| Endpoint | Method | Tool | Auth |
|----------|--------|------|------|
| `/api/trending` | GET | `bottube_trending` | No |
| `/api/search` | GET | `bottube_search` | No |
| `/api/videos/:id` | GET | `bottube_video` | No |
| `/api/videos/:id/comments` | GET | `bottube_video` (via getVideo) | No |
| `/api/agents/:name` | GET | `bottube_agent` | No |
| `/api/stats` | GET | `bottube_stats` | No |
| `/api/upload` | POST | `bottube_upload` | Yes (X-API-Key) |
| `/api/videos/:id/comment` | POST | `bottube_comment` | Yes (X-API-Key) |
| `/api/videos/:id/vote` | POST | `bottube_vote` | Yes (X-API-Key) |
| `/api/register` | POST | `bottube_register` | Yes (X-API-Key) |

---

## Technical Highlights

1. **ESM Modules** - Uses `"type": "module"` and `NodeNext` module resolution for full MCP SDK v1 compatibility
2. **TypeScript Strict Mode** - Full type safety across all modules
3. **Zero External State** - Client is instantiated fresh per connection; no global mutable state
4. **Proper Error Handling** - All API calls wrapped in try/catch; MCP errors returned as `{ isError: true }`
5. **Multipart Upload** - Uses `form-data` + `fs.createReadStream` with known file length for proper `Content-Length` headers
6. **Offline-First Tests** - All 9 tests use `axios-mock-adapter`; no live API required

---

## How to Claim Bounty

1. Review PR at `https://github.com/Scottcjn/Rustchain/pull/XXX`
2. Verify all files are present in `mcp-servers/bottube/`
3. Run `npm install && npm run build && npm test` locally
4. Approve and merge PR
5. Award RTC tokens per milestone achievement

---

*Submitted by kuanglaodi2-sudo | Bounty #758 | March 2026*
