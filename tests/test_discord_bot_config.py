import importlib.util
from pathlib import Path


ENV_KEYS = [
    "DISCORD_TOKEN",
    "DISCORD_GUILD_ID",
    "RUSTCHAIN_NODE_URL",
    "RUSTCHAIN_API_TIMEOUT",
    "BOT_PREFIX",
    "BOT_OWNER_ID",
    "LOG_LEVEL",
]


def load_config_module():
    module_path = Path(__file__).resolve().parents[1] / "discord_bot" / "config.py"
    spec = importlib.util.spec_from_file_location("discord_bot_config", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_from_env_uses_defaults_when_environment_is_missing(monkeypatch):
    module = load_config_module()
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = module.BotConfig.from_env()

    assert config.discord_token == ""
    assert config.discord_guild_id == ""
    assert config.rustchain_node_url == "https://rustchain.org"
    assert config.api_timeout == 10.0
    assert config.prefix == "!"
    assert config.owner_id == ""
    assert config.log_level == "INFO"


def test_from_env_loads_custom_values(monkeypatch):
    module = load_config_module()
    monkeypatch.setenv("DISCORD_TOKEN", "token-123")
    monkeypatch.setenv("DISCORD_GUILD_ID", "guild-456")
    monkeypatch.setenv("RUSTCHAIN_NODE_URL", "https://node.example")
    monkeypatch.setenv("RUSTCHAIN_API_TIMEOUT", "2.5")
    monkeypatch.setenv("BOT_PREFIX", "/")
    monkeypatch.setenv("BOT_OWNER_ID", "owner-789")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    config = module.BotConfig.from_env()

    assert config.discord_token == "token-123"
    assert config.discord_guild_id == "guild-456"
    assert config.rustchain_node_url == "https://node.example"
    assert config.api_timeout == 2.5
    assert config.prefix == "/"
    assert config.owner_id == "owner-789"
    assert config.log_level == "DEBUG"


def test_validate_reports_required_and_timeout_errors():
    module = load_config_module()
    config = module.BotConfig(
        discord_token="",
        rustchain_node_url="",
        api_timeout=0,
    )

    assert config.validate() == [
        "DISCORD_TOKEN is required",
        "RUSTCHAIN_NODE_URL is required",
        "RUSTCHAIN_API_TIMEOUT must be positive",
    ]


def test_validate_accepts_minimum_valid_config():
    module = load_config_module()
    config = module.BotConfig(
        discord_token="token-123",
        rustchain_node_url="https://node.example",
        api_timeout=0.1,
    )

    assert config.validate() == []
