"""
RustChain JSON-RPC API
======================

REST and JSON-RPC endpoints for node interaction.

Endpoints:
- /api/stats - Blockchain statistics
- /api/wallet/:address - Wallet balance
- /api/block/:height - Block data
- /api/mine - Submit mining proof
- /api/governance/* - Governance operations
"""

import json
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading


# =============================================================================
# API Response
# =============================================================================

@dataclass
class ApiResponse:
    """Standard API response"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = int(time.time())

    def to_json(self) -> str:
        return json.dumps({
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp,
        })


# =============================================================================
# RPC Methods Registry
# =============================================================================

class RpcRegistry:
    """Registry for RPC methods"""

    def __init__(self):
        self.methods: Dict[str, Callable] = {}

    def register(self, name: str, handler: Callable):
        """Register an RPC method"""
        self.methods[name] = handler

    def call(self, name: str, params: Dict[str, Any]) -> ApiResponse:
        """Call an RPC method"""
        handler = self.methods.get(name)
        if not handler:
            return ApiResponse(success=False, error=f"Method not found: {name}")

        try:
            result = handler(params)
            return ApiResponse(success=True, data=result)
        except Exception as e:
            return ApiResponse(success=False, error=str(e))


# =============================================================================
# API Server
# =============================================================================

class RustChainApi:
    """
    Main API server for RustChain node.

    Provides REST endpoints and JSON-RPC interface.
    """

    def __init__(self, node):
        """
        Initialize API server.

        Args:
            node: RustChain node instance
        """
        self.node = node
        self.rpc = RpcRegistry()
        self._register_methods()

    def _register_methods(self):
        """Register all RPC methods"""
        # Chain methods
        self.rpc.register("getStats", self._get_stats)
        self.rpc.register("getBlock", self._get_block)
        self.rpc.register("getBlockByHash", self._get_block_by_hash)

        # Wallet methods
        self.rpc.register("getWallet", self._get_wallet)
        self.rpc.register("getBalance", self._get_balance)

        # Mining methods
        self.rpc.register("submitProof", self._submit_proof)
        self.rpc.register("getMiningStatus", self._get_mining_status)
        self.rpc.register("getAntiquityScore", self._get_antiquity_score)

        # Governance methods
        self.rpc.register("createProposal", self._create_proposal)
        self.rpc.register("vote", self._vote)
        self.rpc.register("getProposals", self._get_proposals)
        self.rpc.register("getProposal", self._get_proposal)

        # Node methods
        self.rpc.register("getNodeInfo", self._get_node_info)
        self.rpc.register("getPeers", self._get_peers)
        self.rpc.register("getEntropyProfile", self._get_entropy_profile)

    # =========================================================================
    # Chain Methods
    # =========================================================================

    def _get_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get blockchain statistics"""
        return {
            "chain_id": self.node.chain_id,
            "blocks": self.node.get_block_height(),
            "total_minted": self.node.get_total_minted(),
            "mining_pool": self.node.get_mining_pool(),
            "wallets": self.node.get_wallet_count(),
            "pending_proofs": self.node.get_pending_proofs(),
            "current_block_age": self.node.get_block_age(),
            "next_block_in": self.node.get_time_to_next_block(),
        }

    def _get_block(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get block by height"""
        height = params.get("height", 0)
        return self.node.get_block(height)

    def _get_block_by_hash(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get block by hash"""
        block_hash = params.get("hash", "")
        return self.node.get_block_by_hash(block_hash)

    # =========================================================================
    # Wallet Methods
    # =========================================================================

    def _get_wallet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get wallet details"""
        address = params.get("address", "")
        return self.node.get_wallet(address)

    def _get_balance(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get wallet balance"""
        address = params.get("address", "")
        balance = self.node.get_balance(address)
        return {
            "address": address,
            "balance": balance,
            "balance_rtc": balance / 100_000_000,
        }

    # =========================================================================
    # Mining Methods
    # =========================================================================

    def _submit_proof(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Submit mining proof"""
        return self.node.submit_mining_proof(
            wallet=params.get("wallet", ""),
            hardware_model=params.get("hardware", ""),
            release_year=params.get("release_year", 2000),
            uptime_days=params.get("uptime_days", 0),
            entropy_hash=params.get("entropy_hash", ""),
        )

    def _get_mining_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get current mining status"""
        return self.node.get_mining_status()

    def _get_antiquity_score(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Antiquity Score for hardware"""
        return self.node.calculate_antiquity_score(
            release_year=params.get("release_year", 2000),
            uptime_days=params.get("uptime_days", 0),
        )

    # =========================================================================
    # Governance Methods
    # =========================================================================

    def _create_proposal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create governance proposal"""
        return self.node.create_proposal(
            title=params.get("title", ""),
            description=params.get("description", ""),
            proposal_type=params.get("type", "COMMUNITY"),
            proposer=params.get("proposer", ""),
            contract_hash=params.get("contract_hash"),
        )

    def _vote(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cast vote on proposal"""
        return self.node.vote_proposal(
            proposal_id=params.get("proposal_id", ""),
            voter=params.get("voter", ""),
            support=params.get("support", True),
        )

    def _get_proposals(self, params: Dict[str, Any]) -> list:
        """Get all proposals"""
        return self.node.get_proposals()

    def _get_proposal(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get specific proposal"""
        proposal_id = params.get("proposal_id", "")
        return self.node.get_proposal(proposal_id)

    # =========================================================================
    # Node Methods
    # =========================================================================

    def _get_node_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get node information"""
        return {
            "validator_id": self.node.validator_id,
            "version": self.node.version,
            "chain_id": self.node.chain_id,
            "uptime_seconds": self.node.get_uptime(),
            "is_mining": self.node.is_mining,
        }

    def _get_peers(self, params: Dict[str, Any]) -> list:
        """Get connected peers"""
        return self.node.get_peers()

    def _get_entropy_profile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get node's entropy profile"""
        return self.node.get_entropy_profile()


# =============================================================================
# HTTP Request Handler
# =============================================================================

class ApiRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for API"""

    api: RustChainApi = None  # Set by server

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        response = self._route_request(path, params)
        self._send_response(response)

    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode()

        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            params = {}

        parsed = urlparse(self.path)
        response = self._route_request(parsed.path, params)
        self._send_response(response)

    def _route_request(self, path: str, params: Dict[str, Any]) -> ApiResponse:
        """Route request to appropriate handler"""
        # REST endpoints
        routes = {
            "/api/stats": ("getStats", {}),
            "/api/node/info": ("getNodeInfo", {}),
            "/api/peers": ("getPeers", {}),
            "/api/proposals": ("getProposals", {}),
            "/api/entropy": ("getEntropyProfile", {}),
        }

        # Check static routes
        if path in routes:
            method, default_params = routes[path]
            params.update(default_params)
            return self.api.rpc.call(method, params)

        # Dynamic routes
        if path.startswith("/api/wallet/"):
            address = path.split("/")[-1]
            return self.api.rpc.call("getWallet", {"address": address})

        if path.startswith("/api/block/"):
            height = path.split("/")[-1]
            try:
                return self.api.rpc.call("getBlock", {"height": int(height)})
            except ValueError:
                return self.api.rpc.call("getBlockByHash", {"hash": height})

        if path.startswith("/api/proposal/"):
            proposal_id = path.split("/")[-1]
            return self.api.rpc.call("getProposal", {"proposal_id": proposal_id})

        # POST endpoints
        if path == "/api/mine":
            return self.api.rpc.call("submitProof", params)

        if path == "/api/governance/create":
            return self.api.rpc.call("createProposal", params)

        if path == "/api/governance/vote":
            return self.api.rpc.call("vote", params)

        # JSON-RPC endpoint
        if path == "/rpc":
            method = params.get("method", "")
            rpc_params = params.get("params", {})
            return self.api.rpc.call(method, rpc_params)

        return ApiResponse(success=False, error=f"Unknown endpoint: {path}")

    def _send_response(self, response: ApiResponse):
        """Send HTTP response"""
        self.send_response(200 if response.success else 400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response.to_json().encode())

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


# =============================================================================
# API Server Wrapper
# =============================================================================

class ApiServer:
    """
    HTTP API server for RustChain node.

    Runs in a separate thread to avoid blocking the main node.
    """

    def __init__(self, api: RustChainApi, host: str = "0.0.0.0", port: int = 8085):
        self.api = api
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Start the API server"""
        ApiRequestHandler.api = self.api

        self.server = HTTPServer((self.host, self.port), ApiRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        print(f"API server started at http://{self.host}:{self.port}")
        print(f"  - GET  /api/stats")
        print(f"  - GET  /api/wallet/:address")
        print(f"  - GET  /api/block/:height")
        print(f"  - POST /api/mine")
        print(f"  - POST /api/governance/create")
        print(f"  - POST /api/governance/vote")
        print(f"  - POST /rpc (JSON-RPC)")

    def stop(self):
        """Stop the API server"""
        if self.server:
            self.server.shutdown()
            print("API server stopped")


# =============================================================================
# Mock Node for Testing
# =============================================================================

class MockNode:
    """Mock node for API testing"""

    def __init__(self):
        self.chain_id = 2718
        self.version = "0.1.0"
        self.validator_id = "mock_validator"
        self.is_mining = True
        self._start_time = time.time()

    def get_block_height(self): return 100
    def get_total_minted(self): return 1500.0
    def get_mining_pool(self): return 8387108.0
    def get_wallet_count(self): return 50
    def get_pending_proofs(self): return 5
    def get_block_age(self): return 120
    def get_time_to_next_block(self): return 480
    def get_uptime(self): return int(time.time() - self._start_time)

    def get_block(self, height): return {"height": height, "hash": "abc123"}
    def get_block_by_hash(self, h): return {"height": 100, "hash": h}
    def get_wallet(self, addr): return {"address": addr, "balance": 1000.0}
    def get_balance(self, addr): return 100_000_000_000  # 1000 RTC

    def submit_mining_proof(self, **kwargs): return {"success": True, "message": "Proof accepted"}
    def get_mining_status(self): return {"pending": 5, "time_remaining": 480}
    def calculate_antiquity_score(self, **kwargs): return {"score": 50.0}

    def create_proposal(self, **kwargs): return {"id": "RCP-0001", "status": "SUBMITTED"}
    def vote_proposal(self, **kwargs): return {"success": True}
    def get_proposals(self): return [{"id": "RCP-0001", "title": "Test"}]
    def get_proposal(self, pid): return {"id": pid, "title": "Test Proposal"}

    def get_peers(self): return [{"address": "192.168.1.100:8085"}]
    def get_entropy_profile(self): return {"validator_id": "mock", "confidence": 0.85}


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN API SERVER TEST")
    print("=" * 60)

    node = MockNode()
    api = RustChainApi(node)
    server = ApiServer(api, port=8085)

    server.start()

    print("\nTesting endpoints...")

    # Test RPC calls
    tests = [
        ("getStats", {}),
        ("getWallet", {"address": "RTC1Test"}),
        ("getAntiquityScore", {"release_year": 1992, "uptime_days": 300}),
    ]

    for method, params in tests:
        response = api.rpc.call(method, params)
        print(f"\n{method}: {response.data}")

    print("\nServer running on http://localhost:8085")
    print("Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
