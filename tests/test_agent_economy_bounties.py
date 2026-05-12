from importlib.util import module_from_spec, spec_from_file_location
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def load_bounties_module():
    spec = spec_from_file_location(
        "agent_economy_bounties",
        "sdk/rustchain/agent_economy/bounties.py",
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_bounty_computes_deadline_and_posts_payload():
    bounties = load_bounties_module()
    client = Mock()
    client.config = SimpleNamespace(agent_id="issuer-1")
    client._request.return_value = {"bounty_id": "bounty-1"}

    bounty = bounties.BountyClient(client).create_bounty(
        "Title",
        "Description",
        5.0,
        requirements=["tests"],
        tags=["sdk"],
        deadline_days=7,
    )

    client._request.assert_called_once()
    method, path = client._request.call_args.args
    payload = client._request.call_args.kwargs["json_payload"]

    assert method == "POST"
    assert path == "/api/bounty/create"
    assert payload["issuer_id"] == "issuer-1"
    assert payload["title"] == "Title"
    assert payload["description"] == "Description"
    assert payload["reward"] == 5.0
    assert payload["tier"] == bounties.BountyTier.MEDIUM.value
    assert payload["requirements"] == ["tests"]
    assert payload["tags"] == ["sdk"]
    assert payload["deadline"]

    assert bounty.bounty_id == "bounty-1"
    assert bounty.issuer == "issuer-1"
    assert bounty.deadline is not None


def test_create_bounty_defaults_optional_lists_to_empty_payload_values():
    bounties = load_bounties_module()
    client = Mock()
    client.config = SimpleNamespace(agent_id="issuer-1")
    client._request.return_value = {"bounty_id": "bounty-2"}

    bounty = bounties.BountyClient(client).create_bounty(
        "Default lists",
        "Description",
        3.0,
    )

    payload = client._request.call_args.kwargs["json_payload"]
    assert payload["requirements"] == []
    assert payload["tags"] == []
    assert bounty.requirements == []
    assert bounty.tags == []


def test_create_bounty_requires_configured_agent_id():
    bounties = load_bounties_module()
    client = Mock()
    client.config = SimpleNamespace(agent_id="")

    with pytest.raises(ValueError, match="client must have agent_id configured"):
        bounties.BountyClient(client).create_bounty("Title", "Description", 5.0)

    client._request.assert_not_called()
