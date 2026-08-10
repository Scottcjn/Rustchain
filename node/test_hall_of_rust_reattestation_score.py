"""Re-attestation must refresh rust_score on the live Hall of Rust blueprint.

calculate_rust_score() awards RUST_WEIGHTS['attestation_count'] per attestation, but
the /hall/induct re-attestation branch used to bump total_attestations without ever
writing the score back. The leaderboard sorts on rust_score, so a machine that kept
attesting stayed pinned at its induction-day score forever.
"""

import os
import sqlite3
import sys
import tempfile

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import hall_of_rust
from hall_of_rust import RUST_WEIGHTS, hall_bp, init_hall_tables


MACHINE = {
    'device_model': 'PowerMac3,1',
    'device_arch': 'g4',
    'cpu_serial': 'XYZ-REATTEST-001',
    'miner_id': 'miner-reattest',
}


@pytest.fixture
def client():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_hall_tables(db_path)

    app = Flask(__name__)
    app.config['DB_PATH'] = db_path
    app.config['TESTING'] = True
    app.register_blueprint(hall_bp)

    with app.test_client() as c:
        c.db_path = db_path
        yield c

    os.unlink(db_path)


def _stored_score(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT rust_score, total_attestations FROM hall_of_rust"
        ).fetchone()
    finally:
        conn.close()


def test_reattestation_refreshes_rust_score(client):
    induct = client.post('/hall/induct', json=MACHINE).get_json()
    assert induct['inducted'] is True
    induction_score = induct['rust_score']

    # Same machine attests four more times.
    for _ in range(4):
        again = client.post('/hall/induct', json=MACHINE).get_json()
        assert again['inducted'] is False

    score, attestations = _stored_score(client.db_path)
    assert attestations == 5

    expected = round(induction_score + 4 * RUST_WEIGHTS['attestation_count'], 2)
    assert score == expected, (
        f"rust_score frozen at induction value {induction_score} after 5 attestations "
        f"(stored {score}, expected {expected})"
    )


def test_reattestation_response_reports_current_score(client):
    client.post('/hall/induct', json=MACHINE)
    again = client.post('/hall/induct', json=MACHINE).get_json()

    stored_score, _ = _stored_score(client.db_path)
    assert again['attestation_count'] == 2
    assert again['rust_score'] == stored_score


def test_induction_score_unchanged(client):
    """First induction still scores exactly as before (no regression)."""
    induct = client.post('/hall/induct', json=MACHINE).get_json()
    expected = hall_of_rust.calculate_rust_score({
        'manufacture_year': hall_of_rust.estimate_manufacture_year(
            MACHINE['device_model'], MACHINE['device_arch']),
        'device_arch': MACHINE['device_arch'],
        'device_model': MACHINE['device_model'],
        'total_attestations': 1,
        'id': 1,
    })
    assert induct['rust_score'] == expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
