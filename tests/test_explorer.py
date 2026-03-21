"""Unit tests for ExplorerClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from rustchain.explorer import ExplorerClient
from rustchain.exceptions import APIError, NetworkError


@pytest.fixture
def explorer_client():
    http = AsyncMock()
    return ExplorerClient(http, "http://50.28.86.131:8099")


class TestExplorerBlocks:
    @pytest.mark.asyncio
    async def test_blocks_returns_response(self, explorer_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "blocks": [
                {"hash": "abc", "height": 1, "tx_count": 5},
                {"hash": "def", "height": 2, "tx_count": 3},
            ],
            "total": 2,
            "page": 1,
            "per_page": 20,
        }
        mock_response.raise_for_status = MagicMock()
        explorer_client._http.get = AsyncMock(return_value=mock_response)

        result = await explorer_client.blocks()
        assert len(result.blocks) == 2
        assert result.blocks[0].height == 1
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_blocks_pagination_params(self, explorer_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"blocks": [], "total": 0, "page": 3, "per_page": 50}
        mock_response.raise_for_status = MagicMock()
        explorer_client._http.get = AsyncMock(return_value=mock_response)

        await explorer_client.blocks(page=3, per_page=50)
        call_args = explorer_client._http.get.call_args
        assert call_args.kwargs["params"]["page"] == 3
        assert call_args.kwargs["params"]["per_page"] == 50

    @pytest.mark.asyncio
    async def test_blocks_caps_per_page_at_100(self, explorer_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"blocks": [], "total": 0, "page": 1, "per_page": 100}
        mock_response.raise_for_status = MagicMock()
        explorer_client._http.get = AsyncMock(return_value=mock_response)

        await explorer_client.blocks(per_page=500)
        call_args = explorer_client._http.get.call_args
        assert call_args.kwargs["params"]["per_page"] == 100

    @pytest.mark.asyncio
    async def test_blocks_network_error(self, explorer_client):
        import httpx
        explorer_client._http.get = AsyncMock(side_effect=httpx.TimeoutException())

        with pytest.raises(NetworkError) as exc_info:
            await explorer_client.blocks()
        assert "Timeout" in exc_info.value.message


class TestExplorerTransactions:
    @pytest.mark.asyncio
    async def test_transactions_returns_response(self, explorer_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "transactions": [
                {"tx_hash": "tx1", "from_wallet": "w1", "to_wallet": "w2", "amount": 1.0, "fee": 0.001, "status": "confirmed"},
            ],
            "total": 1,
            "page": 1,
            "per_page": 20,
        }
        mock_response.raise_for_status = MagicMock()
        explorer_client._http.get = AsyncMock(return_value=mock_response)

        result = await explorer_client.transactions()
        assert len(result.transactions) == 1
        assert result.transactions[0].tx_hash == "tx1"
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_transactions_api_error(self, explorer_client):
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        explorer_client._http.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)
        )

        with pytest.raises(APIError) as exc_info:
            await explorer_client.transactions()
        assert exc_info.value.status_code == 404
