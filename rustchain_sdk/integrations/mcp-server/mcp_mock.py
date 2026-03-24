"""Mock mcp module for testing on Python 3.9."""

class Server:
    def __init__(self, name):
        self.name = name
    
    def list_tools(self):
        def decorator(func):
            return func
        return decorator
    
    def list_resources(self):
        def decorator(func):
            return func
        return decorator
    
    def list_resource_templates(self):
        def decorator(func):
            return func
        return decorator
    
    def list_prompts(self):
        def decorator(func):
            return func
        return decorator
    
    def call_tool(self):
        def decorator(func):
            return func
        return decorator
    
    def read_resource(self):
        def decorator(func):
            return func
        return decorator
    
    async def run(self, read_stream, write_stream, options):
        pass
    
    def create_initialization_options(self):
        return {}


class stdio_server:
    async def __aenter__(self):
        return (None, None)
    
    async def __aexit__(self, *args):
        pass


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
