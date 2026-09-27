from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rustchain_org_nginx_proxies_beacon_join_and_atlas_in_all_server_blocks():
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")

    serving_blocks = config.count("location /api/stats {")
    assert serving_blocks == 2
    assert config.count("location = /beacon/join {") == serving_blocks
    assert config.count("location = /beacon/atlas {") == serving_blocks
    assert config.count(
        "proxy_pass http://127.0.0.1:8071/beacon/join;"
    ) == serving_blocks
    assert config.count(
        "proxy_pass http://127.0.0.1:8071/beacon/atlas;"
    ) == serving_blocks
