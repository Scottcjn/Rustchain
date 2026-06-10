from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rustchain_org_nginx_proxies_api_stats_in_all_server_blocks():
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    stats_locations = config.count("location /api/stats {")
    miners_locations = config.count("location /api/miners {")

    assert stats_locations == 2
    assert stats_locations == miners_locations
    assert config.count("proxy_pass http://127.0.0.1:8099/api/stats;") == stats_locations
    assert config.count('add_header Access-Control-Allow-Origin "*" always;') >= stats_locations
