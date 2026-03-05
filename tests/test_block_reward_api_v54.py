"""
Block/Reward API Tests v54 (Bounty #652)

Tests for Block and Reward API endpoints on the RustChain node.
All endpoints are currently unimplemented and should return 404.
"""
import pytest
import requests

BASE_URL = "https://50.28.86.131"

NOT_IMPLEMENTED_ENDPOINTS = [
    "/api/coinbase",
    "/coinbase",
    "/api/supply",
    "/supply",
    "/api/emission",
    "/emission",
]


class TestBlockRewardAPI:
    """Test class for Block/Reward API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.verify = False

    @pytest.mark.parametrize("endpoint", NOT_IMPLEMENTED_ENDPOINTS)
    def test_endpoint_returns_404(self, endpoint):
        """Test that unimplemented endpoints return 404."""
        response = self.session.get(f"{BASE_URL}{endpoint}")
        assert response.status_code == 404, \
            f"Endpoint {endpoint} should return 404, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
