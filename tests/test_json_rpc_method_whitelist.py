import importlib
import sys
from pathlib import Path


RUSTCHAIN_CORE = Path(__file__).resolve().parents[1] / "rips" / "rustchain-core"
sys.path.insert(0, str(RUSTCHAIN_CORE))

rpc = importlib.import_module("api.rpc")


class SpyNode(rpc.MockNode):
    def __init__(self):
        super().__init__()
        self.created_proposals = 0
        self.submitted_proofs = 0
        self.votes = 0

    def create_proposal(self, **kwargs):
        self.created_proposals += 1
        return super().create_proposal(**kwargs)

    def submit_mining_proof(self, **kwargs):
        self.submitted_proofs += 1
        return super().submit_mining_proof(**kwargs)

    def vote_proposal(self, **kwargs):
        self.votes += 1
        return super().vote_proposal(**kwargs)


def make_handler(node):
    handler = object.__new__(rpc.ApiRequestHandler)
    handler.api = rpc.RustChainApi(node)
    return handler


def test_json_rpc_blocks_state_changing_methods():
    node = SpyNode()
    handler = make_handler(node)

    for method in ("createProposal", "submitProof", "vote"):
        response = handler._route_request("/rpc", {"method": method, "params": {}})
        assert response.success is False
        assert response.error == f"Method not allowed: {method}"

    assert node.created_proposals == 0
    assert node.submitted_proofs == 0
    assert node.votes == 0


def test_json_rpc_allows_read_only_methods():
    node = SpyNode()
    handler = make_handler(node)

    stats = handler._route_request("/rpc", {"method": "getStats", "params": {}})
    wallet = handler._route_request(
        "/rpc",
        {"method": "getWallet", "params": {"address": "RTC1Test"}},
    )

    assert stats.success is True
    assert stats.data["chain_id"] == 2718
    assert wallet.success is True
    assert wallet.data["address"] == "RTC1Test"


def test_json_rpc_rejects_non_object_params():
    node = SpyNode()
    handler = make_handler(node)

    response = handler._route_request(
        "/rpc",
        {"method": "getWallet", "params": ["not", "an", "object"]},
    )

    assert response.success is False
    assert response.error == "RPC params must be an object"
