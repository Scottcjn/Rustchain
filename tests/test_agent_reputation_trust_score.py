# SPDX-License-Identifier: MIT
"""Regression tests for GET /agent/reputation/<wallet_id> trust-score math.

Guards against an operator-precedence bug where the rating-bonus ternary
swallowed the whole score for unrated agents (a perfect but unrated record
collapsed to 10 / "risky" instead of 90 / "legendary").
"""
import sqlite3
from pathlib import Path

from flask import Flask

import rip302_agent_economy


def _make_client(tmp_path: Path):
    db_path = tmp_path / "agent_jobs.db"
    app = Flask(__name__)
    rip302_agent_economy.register_agent_economy(app, str(db_path))
    return app, db_path


def _insert_rep(db_path: Path, **cols):
    keys = ", ".join(cols)
    marks = ", ".join("?" for _ in cols)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO agent_reputation ({keys}) VALUES ({marks})",
            tuple(cols.values()),
        )


def test_perfect_unrated_agent_is_legendary_not_risky(tmp_path):
    """A 10/10 completed, undisputed, *unrated* worker must score the success
    component (80) plus the default rating bonus (10) = 90, not just 10."""
    app, db_path = _make_client(tmp_path)
    _insert_rep(
        db_path,
        wallet_id="w1",
        jobs_completed_as_worker=10,
        rating_count=0,
        avg_rating=0,
        first_seen=0,
        last_active=0,
    )
    resp = app.test_client().get("/agent/reputation/w1")
    assert resp.status_code == 200
    rep = resp.get_json()["reputation"]
    assert rep["trust_score"] == 90
    assert rep["trust_level"] == "legendary"


def test_rated_agent_score_still_includes_rating_bonus(tmp_path):
    """Rated path is unaffected: perfect record + 5-star rating stays at 100."""
    app, db_path = _make_client(tmp_path)
    _insert_rep(
        db_path,
        wallet_id="w2",
        jobs_completed_as_worker=10,
        rating_count=3,
        avg_rating=5.0,
        first_seen=0,
        last_active=0,
    )
    resp = app.test_client().get("/agent/reputation/w2")
    rep = resp.get_json()["reputation"]
    assert rep["trust_score"] == 100
    assert rep["trust_level"] == "legendary"
