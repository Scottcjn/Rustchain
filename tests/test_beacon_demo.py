import importlib.util
import json
import sys
import types
from argparse import Namespace
from pathlib import Path


def install_beacon_stubs(monkeypatch, calls):
    beacon_skill = types.ModuleType("beacon_skill")

    class FakeIdentity:
        agent_id = "agent-123"

    class FakeAgentIdentity:
        @staticmethod
        def generate(use_mnemonic=False):
            calls["generate_use_mnemonic"] = use_mnemonic
            return FakeIdentity()

    class FakeHeartbeatManager:
        def __init__(self, data_dir):
            calls["heartbeat_data_dir"] = data_dir

        def build_heartbeat(self, ident, status, health, config):
            calls["heartbeat"] = {
                "agent_id": ident.agent_id,
                "status": status,
                "health": health,
                "config": config,
            }
            return {"payload": "heartbeat"}

    beacon_skill.AgentIdentity = FakeAgentIdentity
    beacon_skill.HeartbeatManager = FakeHeartbeatManager

    codec = types.ModuleType("beacon_skill.codec")
    codec.encode_envelope = lambda payload, version, identity, include_pubkey: "encoded-envelope"
    codec.decode_envelopes = lambda text: [{"decoded": text}]
    codec.verify_envelope = lambda envelope, known_keys=None: True

    contracts = types.ModuleType("beacon_skill.contracts")

    class FakeContractManager:
        def __init__(self, data_dir):
            calls["contract_data_dir"] = data_dir

        def list_agent(self, **kwargs):
            calls["list_agent"] = kwargs
            return {"contract_id": "contract-123"}

        def make_offer(self, contract_id, **kwargs):
            calls["make_offer"] = (contract_id, kwargs)
            return {"offer": "ok"}

        def accept_offer(self, contract_id):
            return {"accepted": contract_id}

        def fund_escrow(self, contract_id, **kwargs):
            calls["fund_escrow"] = (contract_id, kwargs)
            return {"funded": contract_id}

        def activate(self, contract_id):
            return {"active": contract_id}

        def settle(self, contract_id):
            return {"settled": contract_id}

    contracts.ContractManager = FakeContractManager

    transports = types.ModuleType("beacon_skill.transports")
    udp = types.ModuleType("beacon_skill.transports.udp")
    udp.udp_listen = lambda *args, **kwargs: calls.setdefault("udp_listen", (args, kwargs))
    udp.udp_send = lambda *args, **kwargs: calls.setdefault("udp_send", (args, kwargs))

    for name, module in {
        "beacon_skill": beacon_skill,
        "beacon_skill.codec": codec,
        "beacon_skill.contracts": contracts,
        "beacon_skill.transports": transports,
        "beacon_skill.transports.udp": udp,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


def load_beacon_demo(monkeypatch, calls):
    install_beacon_stubs(monkeypatch, calls)
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "beacon_demo"
        / "beacon_demo.py"
    )
    spec = importlib.util.spec_from_file_location("beacon_demo", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_print_writes_sorted_json(monkeypatch, capsys):
    module = load_beacon_demo(monkeypatch, {})

    module._print({"b": 2, "a": 1})

    assert capsys.readouterr().out == '{"a": 1, "b": 2}\n'


def test_cmd_send_heartbeat_builds_and_sends_envelope(monkeypatch, tmp_path, capsys):
    calls = {}
    module = load_beacon_demo(monkeypatch, calls)
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)

    result = module.cmd_send_heartbeat(
        Namespace(host="127.0.0.1", port="38400", status="alive", broadcast=True)
    )

    assert result == 0
    assert calls["generate_use_mnemonic"] is False
    assert calls["heartbeat"]["status"] == "alive"
    udp_args, udp_kwargs = calls["udp_send"]
    assert udp_args == ("127.0.0.1", 38400, b"encoded-envelope")
    assert udp_kwargs == {"broadcast": True}
    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "heartbeat_sent"
    assert event["agent_id"] == "agent-123"
    assert event["envelope"] == "encoded-envelope"


def test_cmd_contracts_demo_runs_lifecycle(monkeypatch, tmp_path, capsys):
    calls = {}
    module = load_beacon_demo(monkeypatch, calls)
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)

    assert module.cmd_contracts_demo(Namespace()) == 0

    event = json.loads(capsys.readouterr().out)
    assert event["event"] == "contracts_demo_done"
    assert event["contract_id"] == "contract-123"
    assert calls["make_offer"][0] == "contract-123"
    assert calls["fund_escrow"][0] == "contract-123"


def test_main_dispatches_contracts_demo_and_creates_state_dir(monkeypatch, tmp_path):
    calls = {}
    module = load_beacon_demo(monkeypatch, calls)
    monkeypatch.setattr(module, "STATE_DIR", tmp_path / "state")

    assert module.main(["contracts-demo"]) == 0

    assert (tmp_path / "state").is_dir()
    assert calls["list_agent"]["agent_id"] == "bcn_demo_seller"
