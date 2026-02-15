import pytest
import respx
from httpx import Response
from rustchain.client import RustChainClient
from rustchain.async_client import AsyncRustChainClient
from rustchain.identity import Identity

@pytest.fixture
def identity():
    # Use a fixed seed for reproducible tests
    seed = "0" * 64
    return Identity.from_seed(seed)

@respx.mock
def test_signed_transfer_sync(identity):
    client = RustChainClient("https://api.rustchain.test", identity=identity)
    address = identity.address
    to_address = "target_address"
    amount = 10.5

    # Mock get_nonce
    respx.get(f"https://api.rustchain.test/wallet/nonce/{address}").mock(
        return_value=Response(200, json={"nonce": 5})
    )

    # Mock signed_transfer
    def transfer_side_effect(request):
        import json
        data = json.loads(request.content)
        assert data["from_address"] == address
        assert data["to_address"] == to_address
        assert data["amount_rtc"] == amount
        assert data["nonce"] == 5
        assert "signature" in data
        assert data["public_key"] == address
        return Response(200, json={"status": "success", "tx_hash": "abc"})

    respx.post("https://api.rustchain.test/wallet/transfer/signed").mock(side_effect=transfer_side_effect)

    result = client.signed_transfer(to_address, amount)
    assert result["status"] == "success"
    assert result["tx_hash"] == "abc"

@pytest.mark.asyncio
@respx.mock
async def test_signed_transfer_async(identity):
    async with AsyncRustChainClient("https://api.rustchain.test", identity=identity) as client:
        address = identity.address
        to_address = "target_address"
        amount = 10.5

        # Mock get_nonce
        respx.get(f"https://api.rustchain.test/wallet/nonce/{address}").mock(
            return_value=Response(200, json={"nonce": 5})
        )

        # Mock signed_transfer
        def transfer_side_effect(request):
            import json
            data = json.loads(request.content)
            assert data["from_address"] == address
            assert data["to_address"] == to_address
            assert data["amount_rtc"] == amount
            assert data["nonce"] == 5
            assert "signature" in data
            assert data["public_key"] == address
            return Response(200, json={"status": "success", "tx_hash": "def"})

        respx.post("https://api.rustchain.test/wallet/transfer/signed").mock(side_effect=transfer_side_effect)

        result = await client.signed_transfer(to_address, amount)
        assert result["status"] == "success"
        assert result["tx_hash"] == "def"
