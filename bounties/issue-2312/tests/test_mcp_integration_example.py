import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "mcp_integration.py"
)


def load_example():
    spec = importlib.util.spec_from_file_location("mcp_integration", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return FakeResponse({"name": "Relic MCP", "tools": {}})

    def post(self, *args, **kwargs):
        self.post_calls.append((args, kwargs))
        return FakeResponse({"ok": True})


def test_mcp_client_uses_timeout_for_manifest_and_tool_calls():
    module = load_example()
    client = module.MCPClient("http://example.test/", timeout=7)
    fake_session = FakeSession()
    client.session = fake_session

    assert client.get_manifest()["name"] == "Relic MCP"
    assert client.call_tool("list_machines", {"available_only": True}) == {"ok": True}

    assert fake_session.get_calls == [
        (("http://example.test/mcp/manifest",), {"timeout": 7})
    ]
    assert fake_session.post_calls == [
        (
            ("http://example.test/mcp/tool",),
            {
                "json": {
                    "tool": "list_machines",
                    "arguments": {"available_only": True},
                },
                "timeout": 7,
            },
        )
    ]
