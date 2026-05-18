from rustchainnode import cli


def test_resolve_node_url_uses_persisted_testnet_default():
    assert cli._resolve_node_url({"testnet": True}) == cli.TESTNET_NODE_URL


def test_resolve_node_url_keeps_custom_testnet_url():
    custom = "http://127.0.0.1:9999"
    assert cli._resolve_node_url({"testnet": True, "node_url": custom}) == custom


def test_resolve_node_url_force_testnet_over_default_mainnet():
    assert cli._resolve_node_url({"node_url": cli.NODE_URL}, force_testnet=True) == cli.TESTNET_NODE_URL
