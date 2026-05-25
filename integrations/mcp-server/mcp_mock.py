"""Mock mcp module for testing on Python 3.9."""

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

    async def run(self, read_stream, write_stream, options):
        """Process JSON-RPC messages from read_stream, dispatching to registered handlers."""
        # Send server info on the initialized notification
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
            if method == "notifications/initialized":
                continue
            if method == "notifications/cancelled":
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
                        result = await self._list_tools_handler()
                    else:
                        result = []

                elif method == "resources/list":
                    if self._list_resources_handler:
                        result = await self._list_resources_handler()
                    else:
                        result = []

                elif method == "resources/templates/list":
                    if self._list_resource_templates_handler:
                        result = await self._list_resource_templates_handler()
                    else:
                        result = []

                elif method == "prompts/list":
                    if self._list_prompts_handler:
                        result = await self._list_prompts_handler()
                    else:
                        result = []

                elif method == "tools/call":
                    if self._call_tool_handler:
                        result = await self._call_tool_handler(
                            params.get("name"), params.get("arguments", {})
                        )
                    else:
                        result = []

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
    
    class Resource:
        def __init__(self, uri, name, description, mimeType):
            self.uri = uri
            self.name = name
            self.description = description
            self.mimeType = mimeType
    
    class ResourceTemplate:
        def __init__(self, uriTemplate, name, description):
            self.uriTemplate = uriTemplate
            self.name = name
            self.description = description
    
    class TextContent:
        def __init__(self, type, text):
            self.type = type
            self.text = text
    
    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema


class server:
    Server = Server
    stdio_server = stdio_server


class types_module:
    Prompt = types.Prompt
    Resource = types.Resource
    ResourceTemplate = types.ResourceTemplate
    TextContent = types.TextContent
    Tool = types.Tool
