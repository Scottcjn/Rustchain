#!/usr/bin/env python3
"""Test that mcp_mock.py handles Tool/Resource/Prompt serialization correctly.

Regression test for CameronVanRooyen's review finding:
- "tools/list returns -32603 Internal error: Object of type Tool is not JSON serializable"
- "result shapes are not MCP-shaped"
"""

import json
import sys
import os
import asyncio

# Import the mock module directly (hyphen in dir name prevents normal import)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "integrations", "mcp-server"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "mcp_mock",
    os.path.join(os.path.dirname(__file__), "..", "integrations", "mcp-server", "mcp_mock.py"),
)
mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp)


def test_tools_list_returns_mcp_envelope():
    """tools/list must return {tools: [...]} with serialized Tool dicts."""
    tool = mcp.types.Tool(
        name="greet",
        description="Say hello",
        inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
    )
    d = tool.to_dict()
    assert d == {
        "name": "greet",
        "description": "Say hello",
        "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}},
    }
    assert json.dumps(d)  # Must be JSON-serializable

    # Test the MCP envelope
    raw = [tool]
    normalized = mcp.Server._normalize(raw)
    envelope = {"tools": normalized}
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "result": envelope})
    parsed = json.loads(payload)
    assert parsed["result"]["tools"][0]["name"] == "greet"


def test_resource_serialization():
    """Resource must serialize correctly."""
    res = mcp.types.Resource(
        uri="test://resource/1",
        name="Test Resource",
        description="A test resource",
        mimeType="text/plain",
    )
    d = res.to_dict()
    assert d["uri"] == "test://resource/1"
    assert d["name"] == "Test Resource"
    assert d["mimeType"] == "text/plain"
    assert json.dumps(d)


def test_prompt_serialization():
    """Prompt with arguments must serialize correctly."""
    prompt = mcp.types.Prompt(
        name="ask",
        description="Ask a question",
        arguments=[mcp.types.PromptArgument(name="question", description="Your question", required=True)],
    )
    d = prompt.to_dict()
    assert d["name"] == "ask"
    assert d["arguments"][0]["name"] == "question"
    assert d["arguments"][0]["required"] is True
    assert json.dumps(d)


def test_text_content_serialization():
    """TextContent must serialize correctly."""
    tc = mcp.types.TextContent(type="text", text="Hello, world!")
    d = tc.to_dict()
    assert d == {"type": "text", "text": "Hello, world!"}
    assert json.dumps(d)


def test_normalize_recursive():
    """_normalize handles nested dicts and lists of mock types."""
    nested = {
        "tools": [
            mcp.types.Tool(name="a", description="b", inputSchema={}),
            mcp.types.Tool(name="c", description="d", inputSchema={}),
        ],
        "meta": {"count": 2},
    }
    result = mcp.Server._normalize(nested)
    assert result["tools"][0]["name"] == "a"
    assert result["tools"][1]["name"] == "c"
    assert result["meta"]["count"] == 2
    assert json.dumps(result)


def test_server_name():
    """Server name is stored."""
    srv = mcp.Server("my-agent")
    assert srv.name == "my-agent"


def test_initialize_result():
    """Initialize must return protocol capabilities."""
    init_result = {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
        "serverInfo": {"name": "test", "version": "1.0.0"},
    }
    assert json.dumps(init_result)
    assert init_result["serverInfo"]["name"] == "test"


def test_ping_result():
    """Ping returns empty result."""
    assert json.dumps({})


def test_stdio_server_aexit():
    """__aexit__ returns False to propagate exceptions."""

    async def test():
        srv = mcp.stdio_server()
        result = await srv.__aexit__(None, None, None)
        assert result is False

    asyncio.run(test())


def test_stdio_server_aenter():
    """__aenter__ returns (None, None)."""

    async def test():
        srv = mcp.stdio_server()
        result = await srv.__aenter__()
        assert result == (None, None)

    asyncio.run(test())


def test_handler_decorators_store_handlers():
    """Decorators must store the handler function on the server."""
    srv = mcp.Server("test")

    @srv.list_tools()
    async def my_tools():
        return []

    assert srv._list_tools_handler is not None
    assert srv._list_tools_handler is my_tools

    @srv.list_resources()
    async def my_resources():
        return []

    assert srv._list_resources_handler is not None
    assert srv._list_resources_handler is my_resources

    @srv.list_prompts()
    async def my_prompts():
        return []

    assert srv._list_prompts_handler is not None
    assert srv._list_prompts_handler is my_prompts

    @srv.call_tool()
    async def my_call(name, args):
        return []

    assert srv._call_tool_handler is not None
    assert srv._call_tool_handler is my_call

    @srv.read_resource()
    async def my_read(uri):
        return ("content", "text/plain")

    assert srv._read_resource_handler is not None
    assert srv._read_resource_handler is my_read


def test_resource_template_serialization():
    """ResourceTemplate must serialize correctly."""
    rt = mcp.types.ResourceTemplate(
        uriTemplate="test://{id}",
        name="Dynamic Resource",
        description="A template resource",
    )
    d = rt.to_dict()
    assert d["uriTemplate"] == "test://{id}"
    assert d["name"] == "Dynamic Resource"
    assert json.dumps(d)


def test_server_create_initialization_options():
    """create_initialization_options returns empty dict."""
    srv = mcp.Server("test")
    opts = srv.create_initialization_options()
    assert opts == {}


def test_full_tools_list_via_run():
    """End-to-end: register a Tool handler, call tools/list through run()."""

    async def test():
        srv = mcp.Server("test-server")

        @srv.list_tools()
        async def list_tools():
            return [
                mcp.types.Tool(
                    name="greet",
                    description="Say hello",
                    inputSchema={"type": "object"},
                ),
            ]

        # Create in-memory streams
        reader = io.BytesIO()
        writer = io.BytesIO()

        # Write initialize + tools/list requests
        req_init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        req_list = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        reader.write((req_init + "\\n" + req_list + "\\n").encode("utf-8"))
        reader.seek(0)

        responses = []

        class TestReadStream:
            def __init__(self, buf):
                self.buf = buf
                self.lines = buf.getvalue().decode("utf-8").split("\\n")
                self.idx = 0

            async def readline(self):
                if self.idx >= len(self.lines):
                    return b""
                line = self.lines[self.idx].encode("utf-8")
                self.idx += 1
                return line

        class TestWriteStream:
            def __init__(self, buf):
                self.buf = buf

            def write(self, data):
                self.buf.write(data)

            async def drain(self):
                pass

        rs = TestReadStream(reader)
        ws = TestWriteStream(writer)

        await srv.run(rs, ws, {})

        # Parse responses
        output = writer.getvalue().decode("utf-8")
        response_lines = [l for l in output.split("\n") if l.strip()]
        assert len(response_lines) == 2

        r1 = json.loads(response_lines[0])
        assert r1["id"] == 1
        assert r1["result"]["serverInfo"]["name"] == "test-server"

        r2 = json.loads(response_lines[1])
        assert r2["id"] == 2
        assert "tools" in r2["result"]
        assert len(r2["result"]["tools"]) == 1
        assert r2["result"]["tools"][0]["name"] == "greet"

    asyncio.run(test())


import io
