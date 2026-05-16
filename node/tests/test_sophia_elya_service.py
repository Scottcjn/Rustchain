from node import sophia_elya_service as elya


def _client():
    elya.app.config["TESTING"] = True
    return elya.app.test_client()


def test_elya_register_requires_json_object():
    resp = _client().post("/api/register", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "json_object_required"


def test_elya_epoch_enroll_rejects_invalid_nested_shapes():
    client = _client()

    weights_resp = client.post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": "ticket-a",
            "weights": ["not", "object"],
        },
    )
    falsey_weights_resp = client.post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": "ticket-a",
            "weights": [],
        },
    )
    device_resp = client.post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": "ticket-a",
            "weights": {},
            "device": [],
        },
    )

    assert weights_resp.status_code == 400
    assert weights_resp.get_json()["reason"] == "invalid_weights"
    assert falsey_weights_resp.status_code == 400
    assert falsey_weights_resp.get_json()["reason"] == "invalid_weights"
    assert device_resp.status_code == 400
    assert device_resp.get_json()["reason"] == "invalid_device"


def test_elya_attest_submit_rejects_non_object_report():
    resp = _client().post("/attest/submit", json={"report": ["not", "object"]})

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_report"


def test_elya_attest_submit_rejects_non_object_report_device():
    resp = _client().post(
        "/attest/submit",
        json={"report": {"commitment": "abc", "device": []}},
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_device"


def test_elya_submit_block_rejects_invalid_header_shapes():
    client = _client()

    header_resp = client.post(
        "/api/submit_block",
        json={"header": ["not", "object"], "header_ext": {}},
    )
    ext_resp = client.post(
        "/api/submit_block",
        json={"header": {"prev_hash_b3": elya.LAST_HASH_B3}, "header_ext": ["bad"]},
    )

    assert header_resp.status_code == 400
    assert header_resp.get_json()["error"] == "invalid_header"
    assert ext_resp.status_code == 400
    assert ext_resp.get_json()["error"] == "invalid_header_ext"
