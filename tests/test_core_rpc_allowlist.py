import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RPC_PATH = REPO_ROOT / "rips" / "rustchain-core" / "api" / "rpc.py"


def load_rpc_module():
    module_name = "rustchain_core_rpc_under_test"
    spec = importlib.util.spec_from_file_location(module_name, RPC_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TrackingNode:
    def __init__(self):
        self.chain_id = 2718
        self.version = "0.1.0"
        self.validator_id = "validator"
        self.is_mining = False
        self.created_proposals = 0
        self.submitted_proofs = 0
        self.votes = 0

    def get_block_height(self):
        return 12

    def get_total_minted(self):
        return 100

    def get_mining_pool(self):
        return 50

    def get_wallet_count(self):
        return 3

    def get_pending_proofs(self):
        return 0

    def get_block_age(self):
        return 10

    def get_time_to_next_block(self):
        return 90

    def get_block(self, height):
        return {"height": height, "hash": "abc"}

    def get_block_by_hash(self, block_hash):
        return {"height": 12, "hash": block_hash}

    def get_wallet(self, address):
        return {"address": address, "balance": 100}

    def get_balance(self, address):
        return 100

    def get_mining_status(self):
        return {"pending": 0}

    def calculate_antiquity_score(self, **kwargs):
        return {"score": 1}

    def get_proposals(self):
        return []

    def get_proposal(self, proposal_id):
        return {"id": proposal_id}

    def get_uptime(self):
        return 1

    def get_peers(self):
        return []

    def get_entropy_profile(self):
        return {"validator_id": self.validator_id}

    def create_proposal(self, **kwargs):
        self.created_proposals += 1
        return {"id": "RCP-1"}

    def submit_mining_proof(self, **kwargs):
        self.submitted_proofs += 1
        return {"success": True}

    def vote_proposal(self, **kwargs):
        self.votes += 1
        return {"success": True}


def route_rpc(params):
    rpc_module = load_rpc_module()
    node = TrackingNode()
    handler = object.__new__(rpc_module.ApiRequestHandler)
    handler.api = rpc_module.RustChainApi(node)
    return handler._route_request("/rpc", params), node


def test_rpc_endpoint_allows_read_only_method():
    response, node = route_rpc({
        "method": "getStats",
        "params": {},
    })

    assert response.success is True
    assert response.data["chain_id"] == 2718
    assert node.created_proposals == 0
    assert node.submitted_proofs == 0
    assert node.votes == 0


def test_rpc_endpoint_blocks_mutating_governance_method():
    response, node = route_rpc({
        "method": "createProposal",
        "params": {"title": "fake proposal", "proposer": "attacker"},
    })

    assert response.success is False
    assert response.error == "Method not allowed via /rpc: createProposal"
    assert node.created_proposals == 0


def test_rpc_endpoint_blocks_mutating_mining_method():
    response, node = route_rpc({
        "method": "submitProof",
        "params": {"wallet": "attacker"},
    })

    assert response.success is False
    assert response.error == "Method not allowed via /rpc: submitProof"
    assert node.submitted_proofs == 0


def test_rpc_endpoint_blocks_mutating_vote_method():
    response, node = route_rpc({
        "method": "vote",
        "params": {"proposal_id": "RCP-1", "voter": "attacker"},
    })

    assert response.success is False
    assert response.error == "Method not allowed via /rpc: vote"
    assert node.votes == 0
