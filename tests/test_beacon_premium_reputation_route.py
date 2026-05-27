import sys


integrated_node = sys.modules["integrated_node"]


def test_premium_reputation_route_is_registered():
    integrated_node.app.config["TESTING"] = True
    response = integrated_node.app.test_client().get("/api/premium/reputation")

    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 0
    assert data["reputation"] == []
    assert "exported_at" in data
