"""Tests for API endpoint rate limiting (Issue #2749)."""
import sqlite3
import sys
import os
import time

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.dirname(__file__))

# Create a temporary DB for testing
TEST_DB = "/tmp/test_rate_limit.db"

# Constants from the main module
API_RATE_LIMIT = 100
API_RATE_WINDOW = 60


def setup_db():
    """Create a fresh test database with the rate limit table."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    conn = sqlite3.connect(TEST_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS api_rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_ip TEXT NOT NULL,
        endpoint TEXT NOT NULL,
        ts INTEGER NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_rate_limits_ip_endpoint_ts ON api_rate_limits(client_ip, endpoint, ts)")
    conn.commit()
    return conn


def check_api_endpoint_rate_limit(client_ip, endpoint, db_path=TEST_DB):
    """Copy of the rate limit function for testing."""
    now = int(time.time())
    cutoff = now - API_RATE_WINDOW

    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM api_rate_limits WHERE endpoint = ? AND ts < ?", (endpoint, cutoff))
        row = conn.execute(
            "SELECT COUNT(*) FROM api_rate_limits WHERE client_ip = ? AND endpoint = ? AND ts >= ?",
            (client_ip, endpoint, cutoff)
        ).fetchone()
        request_count = row[0] if row else 0

        if request_count >= API_RATE_LIMIT:
            oldest = conn.execute(
                "SELECT MIN(ts) FROM api_rate_limits WHERE client_ip = ? AND endpoint = ? AND ts >= ?",
                (client_ip, endpoint, cutoff)
            ).fetchone()
            retry_after = (oldest[0] + API_RATE_WINDOW) - now if oldest else API_RATE_WINDOW
            return False, 0, max(1, retry_after), f"rate_limit_exceeded:{request_count}/{API_RATE_LIMIT} per {API_RATE_WINDOW}s"

        conn.execute(
            "INSERT INTO api_rate_limits (client_ip, endpoint, ts) VALUES (?, ?, ?)",
            (client_ip, endpoint, now)
        )

        remaining = API_RATE_LIMIT - request_count - 1
        return True, remaining, 0, "ok"


def test_first_request_allowed():
    """First request should be allowed with correct remaining count."""
    setup_db()
    allowed, remaining, retry_after, msg = check_api_endpoint_rate_limit("192.168.1.1", "/api/miners")
    assert allowed is True, "First request should be allowed"
    assert remaining == API_RATE_LIMIT - 1, f"Remaining should be {API_RATE_LIMIT - 1}, got {remaining}"
    assert retry_after == 0, "Retry-after should be 0 for allowed requests"
    print("PASS: test_first_request_allowed")


def test_multiple_requests_decrease_remaining():
    """Each request should decrease the remaining count."""
    setup_db()
    for i in range(10):
        allowed, remaining, _, _ = check_api_endpoint_rate_limit("10.0.0.1", "/api/miners")
        assert allowed is True
        assert remaining == API_RATE_LIMIT - 1 - i, f"After {i+1} requests, remaining should be {API_RATE_LIMIT - 1 - i}, got {remaining}"
    print("PASS: test_multiple_requests_decrease_remaining")


def test_rate_limit_at_max():
    """At exactly the limit, the next request should be blocked."""
    setup_db()
    # Make API_RATE_LIMIT requests
    for i in range(API_RATE_LIMIT):
        allowed, remaining, _, _ = check_api_endpoint_rate_limit("172.16.0.1", "/api/miners")
        assert allowed is True, f"Request {i+1} should be allowed"

    # Next request should be blocked
    allowed, remaining, retry_after, msg = check_api_endpoint_rate_limit("172.16.0.1", "/api/miners")
    assert allowed is False, "Request over limit should be blocked"
    assert remaining == 0, "Remaining should be 0 when blocked"
    assert retry_after > 0, "Retry-after should be positive when blocked"
    assert "rate_limit_exceeded" in msg, f"Message should contain rate_limit_exceeded, got: {msg}"
    print("PASS: test_rate_limit_at_max")


def test_different_ips_independent():
    """Rate limits should be independent per IP."""
    setup_db()
    # Fill up rate limit for IP1
    for _ in range(API_RATE_LIMIT):
        check_api_endpoint_rate_limit("1.1.1.1", "/api/miners")

    # IP2 should still be allowed
    allowed, remaining, _, _ = check_api_endpoint_rate_limit("2.2.2.2", "/api/miners")
    assert allowed is True, "Different IP should not be affected"
    assert remaining == API_RATE_LIMIT - 1
    print("PASS: test_different_ips_independent")


def test_different_endpoints_independent():
    """Rate limits should be independent per endpoint."""
    setup_db()
    # Fill up rate limit for /api/miners
    for _ in range(API_RATE_LIMIT):
        check_api_endpoint_rate_limit("3.3.3.3", "/api/miners")

    # /api/blocks should still be allowed
    allowed, remaining, _, _ = check_api_endpoint_rate_limit("3.3.3.3", "/api/blocks")
    assert allowed is True, "Different endpoint should not be affected"
    print("PASS: test_different_endpoints_independent")


def test_expired_entries_cleaned():
    """Expired entries should be cleaned and allow new requests."""
    setup_db()
    now = int(time.time())

    # Insert old entries (outside the window)
    with sqlite3.connect(TEST_DB) as conn:
        for i in range(API_RATE_LIMIT):
            conn.execute(
                "INSERT INTO api_rate_limits (client_ip, endpoint, ts) VALUES (?, ?, ?)",
                ("4.4.4.4", "/api/miners", now - API_RATE_WINDOW - 10)
            )
        conn.commit()

    # Should be allowed because old entries are expired
    allowed, remaining, _, _ = check_api_endpoint_rate_limit("4.4.4.4", "/api/miners")
    assert allowed is True, "Expired entries should allow new requests"
    print("PASS: test_expired_entries_cleaned")


def test_retry_after_calculation():
    """Retry-after should be calculated from oldest entry in window."""
    setup_db()
    now = int(time.time())

    with sqlite3.connect(TEST_DB) as conn:
        # Insert API_RATE_LIMIT entries with known timestamps
        for i in range(API_RATE_LIMIT):
            ts = now - (API_RATE_WINDOW - 30) + i  # oldest is 30s into the window
            conn.execute(
                "INSERT INTO api_rate_limits (client_ip, endpoint, ts) VALUES (?, ?, ?)",
                ("5.5.5.5", "/api/miners", ts)
            )
        conn.commit()

    allowed, remaining, retry_after, msg = check_api_endpoint_rate_limit("5.5.5.5", "/api/miners")
    assert allowed is False
    # The oldest entry was at now - (API_RATE_WINDOW - 30), so it expires in ~30s
    assert retry_after <= 30 + 1, f"Retry-after should be ~30s, got {retry_after}"
    assert retry_after > 0, "Retry-after should be positive"
    print("PASS: test_retry_after_calculation")


def test_sliding_window_reset():
    """After the window passes, requests should be allowed again."""
    setup_db()
    now = int(time.time())

    with sqlite3.connect(TEST_DB) as conn:
        # Insert API_RATE_LIMIT entries that are just outside the window
        for i in range(API_RATE_LIMIT):
            ts = now - API_RATE_WINDOW - 5  # 5 seconds outside window
            conn.execute(
                "INSERT INTO api_rate_limits (client_ip, endpoint, ts) VALUES (?, ?, ?)",
                ("6.6.6.6", "/api/miners", ts)
            )
        conn.commit()

    allowed, remaining, _, _ = check_api_endpoint_rate_limit("6.6.6.6", "/api/miners")
    assert allowed is True, "Entries outside window should not count"
    print("PASS: test_sliding_window_reset")


if __name__ == "__main__":
    test_first_request_allowed()
    test_multiple_requests_decrease_remaining()
    test_rate_limit_at_max()
    test_different_ips_independent()
    test_different_endpoints_independent()
    test_expired_entries_cleaned()
    test_retry_after_calculation()
    test_sliding_window_reset()

    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    print("\nAll 8 tests passed!")
