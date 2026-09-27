from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_beacon_join_and_atlas_preserve_server_security_headers():
    config = (ROOT / "site" / "nginx-rustchain-org.conf").read_text(encoding="utf-8")
    required = (
        'add_header X-Frame-Options "SAMEORIGIN" always;',
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-RustChain "Proof-of-Antiquity" always;',
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;',
        'add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;',
        "add_header Content-Security-Policy \"default-src 'self';",
        'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
        'add_header X-XSS-Protection "1; mode=block" always;',
    )

    for path in ("/beacon/join", "/beacon/atlas"):
        blocks = config.split(f"location = {path} {{")[1:]
        assert len(blocks) == 2
        for block in blocks:
            before_options = block.split("if ($request_method = OPTIONS)", 1)[0]
            for header in required:
                assert header in before_options, f"{path} is missing {header}"


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
