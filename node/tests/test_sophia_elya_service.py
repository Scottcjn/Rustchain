import sqlite3
import time

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


def test_elya_epoch_enroll_rejects_invalid_slot_before_consuming_ticket():
    ticket_id = "slot-validation-ticket"
    elya.tickets_db[ticket_id] = {"expires_at": time.time() + 60}

    resp = _client().post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": ticket_id,
            "slot": "not-an-integer",
        },
    )

    assert resp.status_code == 400
    assert resp.get_json() == {"ok": False, "reason": "invalid_slot"}
    assert ticket_id in elya.tickets_db


def test_elya_epoch_enroll_rejects_invalid_weights_before_consuming_ticket():
    ticket_id = "weight-validation-ticket"
    elya.tickets_db[ticket_id] = {"expires_at": time.time() + 60}

    resp = _client().post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": ticket_id,
            "weights": {"temporal": "inf"},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json() == {"ok": False, "reason": "invalid_weights"}
    assert ticket_id in elya.tickets_db


def test_elya_epoch_enroll_rejects_negative_weight_before_consuming_ticket():
    ticket_id = "negative-weight-ticket"
    elya.tickets_db[ticket_id] = {"expires_at": time.time() + 60}

    resp = _client().post(
        "/epoch/enroll",
        json={
            "miner_pubkey": "miner-a",
            "ticket_id": ticket_id,
            "weights": {"temporal": -5.0},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json() == {"ok": False, "reason": "invalid_weights"}
    # A rejected request must not burn the ticket.
    assert ticket_id in elya.tickets_db


def test_enroll_epoch_ignores_non_positive_weight():
    # Backstop: even a direct call must never persist a non-positive weight,
    # which would shrink sum_w at settlement and amplify other payouts.
    elya.init_db()
    epoch = 990001
    elya.enroll_epoch(epoch, "miner-neg", -3.0)
    elya.enroll_epoch(epoch, "miner-zero", 0.0)
    elya.enroll_epoch(epoch, "miner-ok", 2.0)

    with sqlite3.connect(elya.DB_PATH) as conn:
        rows = dict(
            conn.execute(
                "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch=?", (epoch,)
            )
        )

    assert rows == {"miner-ok": 2.0}


def test_finalize_epoch_excludes_poisoned_negative_weight_rows():
    # A poisoned legacy row (negative weight written before the guard existed)
    # must not shrink sum_w and inflate the honest miner's payout.
    elya.init_db()
    epoch = 990002
    with sqlite3.connect(elya.DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)",
            (epoch, "honest", 1.0),
        )
        conn.execute(
            "INSERT OR REPLACE INTO epoch_enroll(epoch, miner_pk, weight) VALUES (?,?,?)",
            (epoch, "poisoned", -9.0),
        )
        conn.execute(
            "INSERT OR IGNORE INTO epoch_state(epoch, accepted_blocks, finalized, settled) "
            "VALUES (?,?,0,0)",
            (epoch, 1),
        )
        conn.commit()

    result = elya.finalize_epoch(epoch, per_block_rtc=10.0)

    assert result["ok"] is True
    # sum_w counts only the honest positive weight, so the whole reward goes
    # to the honest miner instead of being amplified by the negative row.
    assert result["sum_w"] == 1.0
    paid = dict(result["payouts"])
    assert set(paid) == {"honest"}


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


def test_elya_submit_block_rejects_invalid_ticket_shape():
    resp = _client().post(
        "/api/submit_block",
        json={
            "header": {"prev_hash_b3": elya.LAST_HASH_B3},
            "header_ext": {"ticket": ["bad"]},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_ticket"


def test_elya_submit_block_rejects_invalid_slot():
    resp = _client().post(
        "/api/submit_block",
        json={
            "header": {"prev_hash_b3": elya.LAST_HASH_B3, "slot": "NaN"},
            "header_ext": {},
        },
    )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_slot"
