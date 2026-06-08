from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rustchain_org_nginx_proxies_network_and_peers_in_all_server_blocks():
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    for route in ("network", "peers"):
        locations = config.count(f"location /api/{route} {{")
        assert locations == 2
        assert config.count(f"proxy_pass http://127.0.0.1:8099/api/{route};") == locations
