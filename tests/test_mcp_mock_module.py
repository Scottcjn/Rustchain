import asyncio
import importlib.util
from pathlib import Path


def load_mcp_mock():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "mcp-server"
        / "mcp_mock.py"
    )
    spec = importlib.util.spec_from_file_location("mcp_mock_module", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_server_decorators_return_original_function():
    module = load_mcp_mock()
    server = module.Server("rustchain")

    def handler():
        return "handled"

    for decorator_factory in [
        server.list_tools,
        server.list_resources,
        server.list_resource_templates,
        server.list_prompts,
        server.call_tool,
        server.read_resource,
    ]:
        decorated = decorator_factory()(handler)
        assert decorated is handler
        assert decorated() == "handled"


def test_server_initialization_options_are_empty():
    module = load_mcp_mock()
    server = module.Server("rustchain")

    assert server.name == "rustchain"
    assert server.create_initialization_options() == {}


def test_stdio_server_context_manager_returns_empty_streams():
    module = load_mcp_mock()

    async def run_context():
        async with module.stdio_server() as streams:
            return streams

    assert asyncio.run(run_context()) == (None, None)


def test_mock_type_containers_store_constructor_values():
    module = load_mcp_mock()

    prompt = module.types.Prompt("p", "desc", arguments=["arg"])
    resource = module.types.Resource("uri://x", "resource", "desc", "text/plain")
    template = module.types.ResourceTemplate("uri://{id}", "template", "desc")
    content = module.types.TextContent("text", "hello")
    tool = module.types.Tool("tool", "desc", {"type": "object"})

    assert prompt.name == "p"
    assert prompt.description == "desc"
    assert prompt.arguments == ["arg"]
    assert resource.uri == "uri://x"
    assert resource.name == "resource"
    assert resource.description == "desc"
    assert resource.mimeType == "text/plain"
    assert template.uriTemplate == "uri://{id}"
    assert template.name == "template"
    assert template.description == "desc"
    assert content.type == "text"
    assert content.text == "hello"
    assert tool.name == "tool"
    assert tool.description == "desc"
    assert tool.inputSchema == {"type": "object"}


def test_module_level_aliases_match_mock_classes():
    module = load_mcp_mock()

    assert module.server.Server is module.Server
    assert module.server.stdio_server is module.stdio_server
    assert module.types_module.Prompt is module.types.Prompt
    assert module.types_module.Tool is module.types.Tool
