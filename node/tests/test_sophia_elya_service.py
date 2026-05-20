from node import sophia_elya_service as elya


def _client():
    elya.app.config["TESTING"] = True
    return elya.app.test_client()


def _mint_ticket(client, commitment="commitment"):
    resp = client.post(
        "/attest/submit",
        json={"report": {"commitment": commitment, "device": {"family": "x86"}}},
    )
    assert resp.status_code == 200
    return resp.get_json()["ticket_id"]


def _use_temp_db(tmp_path):
    old_db_path = elya.DB_PATH
    elya.DB_PATH = str(tmp_path / "elya.db")
    elya.tickets_db.clear()
    elya.init_db()
    return old_db_path


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


def test_elya_epoch_enroll_rejects_malformed_slot_before_ticket_burn(tmp_path):
    old_db_path = _use_temp_db(tmp_path)
    try:
        client = _client()
        ticket_id = _mint_ticket(client, "bad-slot")

        resp = client.post(
            "/epoch/enroll",
            json={
                "miner_pubkey": "miner-a",
                "ticket_id": ticket_id,
                "weights": {},
                "device": {},
                "slot": "not-an-int",
            },
        )

        assert resp.status_code == 400
        assert resp.get_json()["reason"] == "invalid_slot"
        assert ticket_id in elya.tickets_db
    finally:
        elya.DB_PATH = old_db_path
        elya.tickets_db.clear()


def test_elya_epoch_enroll_rejects_non_finite_and_malformed_weights(tmp_path):
    old_db_path = _use_temp_db(tmp_path)
    try:
        client = _client()
        for idx, value in enumerate(("nan", "inf", "1e309", {}, True)):
            ticket_id = _mint_ticket(client, f"bad-weight-{idx}")
            resp = client.post(
                "/epoch/enroll",
                json={
                    "miner_pubkey": f"miner-{idx}",
                    "ticket_id": ticket_id,
                    "weights": {"temporal": value, "rtc": 1},
                    "device": {},
                },
            )

            assert resp.status_code == 400
            assert resp.get_json()["reason"] == "invalid_weights"
            assert ticket_id in elya.tickets_db
    finally:
        elya.DB_PATH = old_db_path
        elya.tickets_db.clear()


def test_elya_attest_submit_handles_malformed_hardware_weight_fields():
    resp = _client().post(
        "/attest/submit",
        json={
            "report": {
                "commitment": "bad-hardware-weight",
                "device": {"family": [], "arch": []},
            }
        },
    )

    assert resp.status_code == 200
    assert resp.get_json()["weight"] == 1.0


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


def test_elya_submit_block_rejects_malformed_slot_and_ticket_shape():
    client = _client()

    slot_resp = client.post(
        "/api/submit_block",
        json={
            "header": {"prev_hash_b3": elya.LAST_HASH_B3, "slot": "not-an-int"},
            "header_ext": {},
        },
    )
    ticket_resp = client.post(
        "/api/submit_block",
        json={
            "header": {"prev_hash_b3": elya.LAST_HASH_B3, "slot": 1},
            "header_ext": {"ticket": ["not", "an", "object"]},
        },
    )
    ticket_id_resp = client.post(
        "/api/submit_block",
        json={
            "header": {"prev_hash_b3": elya.LAST_HASH_B3, "slot": 1},
            "header_ext": {"ticket": {"ticket_id": ["bad"]}},
        },
    )

    assert slot_resp.status_code == 400
    assert slot_resp.get_json()["error"] == "invalid_slot"
    assert ticket_resp.status_code == 400
    assert ticket_resp.get_json()["error"] == "invalid_ticket"
    assert ticket_id_resp.status_code == 400
    assert ticket_id_resp.get_json()["error"] == "invalid_ticket"
