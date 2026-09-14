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


def test_rustchain_org_nginx_proxies_ready_and_api_nodes():
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    ready_locations = config.count("location /ready {")
    api_nodes_locations = config.count("location /api/nodes {")

    assert ready_locations == 2
    assert api_nodes_locations == 2
    assert config.count("proxy_pass http://127.0.0.1:8099/ready;") == 2
    assert config.count("proxy_pass http://127.0.0.1:8099/api/nodes;") == 2


def test_rustchain_org_nginx_beacon_join_routed_to_atlas_in_all_server_blocks():
    """Bounty #2127: POST /beacon/join must reach the Atlas API on 8071."""
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    join_locations = config.count("location = /beacon/join {")

    assert join_locations == 2
    assert config.count("proxy_pass http://127.0.0.1:8071/beacon/join;") == join_locations
    assert config.count('add_header Access-Control-Allow-Methods "POST, OPTIONS" always;') >= join_locations


def test_rustchain_org_nginx_beacon_atlas_routed_to_atlas_in_all_server_blocks():
    """Bounty #2127: GET /beacon/atlas must reach the Atlas API on 8071."""
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    atlas_locations = config.count("location = /beacon/atlas {")

    assert atlas_locations == 2
    assert config.count("proxy_pass http://127.0.0.1:8071/beacon/atlas;") == atlas_locations
    assert config.count('add_header Access-Control-Allow-Methods "GET, OPTIONS" always;') >= atlas_locations
