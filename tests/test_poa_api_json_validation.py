import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def import_path_and_optional_deps(monkeypatch):
    monkeypatch.syspath_prepend(str(REPO_ROOT / "rips" / "python"))
    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_cors", flask_cors)


class NodeStub:
    def submit_mining_proof(self, wallet, hardware):
        return {
            "ok": True,
            "wallet": wallet.address,
            "hardware": hardware.cpu_model,
            "release_year": hardware.release_year,
        }

    def get_node_antiquity(self, wallet, hardware):
        return {"wallet": wallet.address, "hardware": hardware.cpu_model}

    def create_proposal(
        self,
        title,
        description,
        proposal_type,
        proposer,
        contract_hash=None,
    ):
        return {
            "title": title,
            "description": description,
            "proposal_type": proposal_type,
            "proposer": proposer.address,
            "contract_hash": contract_hash,
        }

    def vote_proposal(self, proposal_id, voter, support):
        return {
            "proposal_id": proposal_id,
            "voter": voter.address,
            "support": support,
        }

    def get_stats(self):
        return {}

    def get_wallet(self, address):
        return {"address": address}

    def get_block(self, height):
        return None

    def get_proposals(self):
        return []


@pytest.fixture
def client():
    from rustchain.node import create_api_server

    app = create_api_server(NodeStub())
    return app.test_client()


@pytest.mark.parametrize(
    "path",
    (
        "/api/mine",
        "/api/node/antiquity",
        "/api/governance/create",
        "/api/governance/vote",
    ),
)
def test_post_routes_reject_non_object_json(client, path):
    response = client.post(path, json=["not", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}


@pytest.mark.parametrize(
    "path, payload, missing",
    (
        ("/api/mine", {"wallet": "RTCminer"}, ["hardware"]),
        ("/api/node/antiquity", {"hardware": "486DX"}, ["wallet"]),
        (
            "/api/governance/create",
            {"title": "T", "description": "D", "proposer": "RTCminer"},
            ["type"],
        ),
        ("/api/governance/vote", {"proposal_id": "p1", "support": True}, ["voter"]),
    ),
)
def test_post_routes_report_missing_fields(client, path, payload, missing):
    response = client.post(path, json=payload)

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Missing required fields",
        "fields": missing,
    }


def test_mine_accepts_valid_json_body(client):
    response = client.post(
        "/api/mine",
        json={
            "wallet": "RTCminer",
            "hardware": "486DX",
            "release_year": 1993,
            "uptime_days": 7,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "wallet": "RTCminer",
        "hardware": "486DX",
        "release_year": 1993,
    }


def test_governance_vote_accepts_valid_json_body(client):
    response = client.post(
        "/api/governance/vote",
        json={"proposal_id": "p1", "voter": "RTCminer", "support": False},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "proposal_id": "p1",
        "voter": "RTCminer",
        "support": False,
    }
