"""Mock mcp module for testing on Python 3.9.

Provides mock MCP server types with JSON-serializable dict conversion
(to_dict) and proper MCP response envelope shapes.

Usage:
    server = mcp.Server("test")
    @server.list_tools()
    async def list_tools():
        return [mcp.types.Tool(
            name="greet",
            description="Say hello",
            inputSchema={"type": "object", "properties": {"name": {"type": "string"}}}
        )]
    # run() will auto-wrap in {"tools": [...]}
"""

import json


class Server:
    def __init__(self, name):
        self.name = name
        self._list_tools_handler = None
        self._list_resources_handler = None
        self._list_resource_templates_handler = None
        self._list_prompts_handler = None
        self._call_tool_handler = None
        self._read_resource_handler = None

    def list_tools(self):
        def decorator(func):
            self._list_tools_handler = func
            return func
        return decorator

    def list_resources(self):
        def decorator(func):
            self._list_resources_handler = func
            return func
        return decorator

    def list_resource_templates(self):
        def decorator(func):
            self._list_resource_templates_handler = func
            return func
        return decorator

    def list_prompts(self):
        def decorator(func):
            self._list_prompts_handler = func
            return func
        return decorator

    def call_tool(self):
        def decorator(func):
            self._call_tool_handler = func
            return func
        return decorator

    def read_resource(self):
        def decorator(func):
            self._read_resource_handler = func
            return func
        return decorator

    @staticmethod
    def _normalize(obj):
        """Convert mock types to dicts recursively for JSON serialization."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, dict):
            return {k: Server._normalize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [Server._normalize(item) for item in obj]
        return obj

    async def run(self, read_stream, write_stream, options):
        """Process JSON-RPC messages from read_stream, dispatching to registered handlers."""
        while True:
            line = await read_stream.readline()
            if not line:
                break

            try:
                msg = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            req_id = msg.get("id")
            method = msg.get("method", "")
            params = msg.get("params", {})

            # Notifications have no id — skip response
            if method in ("notifications/initialized", "notifications/cancelled"):
                continue

            try:
                result = None
                if method == "initialize":
                    result = {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {},
                        },
                        "serverInfo": {"name": self.name, "version": "1.0.0"},
                    }

                elif method == "tools/list":
                    if self._list_tools_handler:
                        raw = await self._list_tools_handler()
                    else:
                        raw = []
                    result = {"tools": self._normalize(raw)}

                elif method == "resources/list":
                    if self._list_resources_handler:
                        raw = await self._list_resources_handler()
                    else:
                        raw = []
                    result = {"resources": self._normalize(raw)}

                elif method == "resources/templates/list":
                    if self._list_resource_templates_handler:
                        raw = await self._list_resource_templates_handler()
                    else:
                        raw = []
                    result = {"resourceTemplates": self._normalize(raw)}

                elif method == "prompts/list":
                    if self._list_prompts_handler:
                        raw = await self._list_prompts_handler()
                    else:
                        raw = []
                    result = {"prompts": self._normalize(raw)}

                elif method == "tools/call":
                    if self._call_tool_handler:
                        raw = await self._call_tool_handler(
                            params.get("name"), params.get("arguments", {})
                        )
                    else:
                        raw = []
                    result = {"content": self._normalize(raw) if not isinstance(raw, dict) else raw}

                elif method == "resources/read":
                    if self._read_resource_handler:
                        content, mime_type = await self._read_resource_handler(params.get("uri"))
                        result = {"contents": [{"uri": params.get("uri"), "mimeType": mime_type, "text": content}]}
                    else:
                        result = {"contents": []}

                elif method == "ping":
                    result = {}

                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                    write_stream.write((json.dumps(response) + "\n").encode("utf-8"))
                    await write_stream.drain()
                    continue

                response = {"jsonrpc": "2.0", "id": req_id, "result": result}
                write_stream.write((json.dumps(response) + "\n").encode("utf-8"))
                await write_stream.drain()

            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                }
                try:
                    write_stream.write((json.dumps(error_response) + "\n").encode("utf-8"))
                    await write_stream.drain()
                except Exception:
                    break

    def create_initialization_options(self):
        return {}


class stdio_server:
    async def __aenter__(self):
        return (None, None)

    async def __aexit__(self, *args):
        """Clean exit — do not suppress any exception."""
        return False


class types:
    class Prompt:
        def __init__(self, name, description, arguments=None):
            self.name = name
            self.description = description
            self.arguments = arguments or []

        def to_dict(self):
            return {
                "name": self.name,
                "description": self.description,
                "arguments": [
                    a.to_dict() if hasattr(a, "to_dict") else a
                    for a in self.arguments
                ],
            }

    class PromptArgument:
        def __init__(self, name, description=None, required=False):
            self.name = name
            self.description = description
            self.required = required

        def to_dict(self):
            d = {"name": self.name}
            if self.description:
                d["description"] = self.description
            if self.required:
                d["required"] = True
            return d

    class Resource:
        def __init__(self, uri, name, description, mimeType):
            self.uri = uri
            self.name = name
            self.description = description
            self.mimeType = mimeType

        def to_dict(self):
            return {
                "uri": self.uri,
                "name": self.name,
                "description": self.description,
                "mimeType": self.mimeType,
            }

    class ResourceTemplate:
        def __init__(self, uriTemplate, name, description):
            self.uriTemplate = uriTemplate
            self.name = name
            self.description = description

        def to_dict(self):
            return {
                "uriTemplate": self.uriTemplate,
                "name": self.name,
                "description": self.description,
            }

    class TextContent:
        def __init__(self, type, text):
            self.type = type
            self.text = text

        def to_dict(self):
            return {"type": self.type, "text": self.text}

    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema

        def to_dict(self):
            return {
                "name": self.name,
                "description": self.description,
                "inputSchema": self.inputSchema,
            }


class server:
    Server = Server
    stdio_server = stdio_server


class types_module:
    Prompt = types.Prompt
    PromptArgument = types.PromptArgument
    Resource = types.Resource
    ResourceTemplate = types.ResourceTemplate
    TextContent = types.TextContent
    Tool = types.Tool
