import importlib.util
import sys
import types
from pathlib import Path


dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_module)

telegram_module = types.ModuleType("telegram")
telegram_module.Update = object
telegram_ext_module = types.ModuleType("telegram.ext")
telegram_ext_module.ApplicationBuilder = object
telegram_ext_module.CommandHandler = object
telegram_ext_module.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
telegram_ext_module.JobQueue = object
sys.modules.setdefault("telegram", telegram_module)
sys.modules.setdefault("telegram.ext", telegram_ext_module)

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "wrtc-price-bot" / "bot.py"
spec = importlib.util.spec_from_file_location("wrtc_price_bot", MODULE_PATH)
wrtc_price_bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrtc_price_bot)


def test_format_price_message_escapes_markdown_link_url():
    message = wrtc_price_bot.format_price_message({
        "price_usd": 0.1234,
        "price_native": "0.001",
        "h24_change": 1.5,
        "h1_change": -0.25,
        "liquidity_usd": 1000,
        "volume_h24": 250,
        "url": "https://example.test/path) injected text",
    })

    assert "[View on DexScreener](https://example.test/path%29%20injected%20text)" in message
    assert "[View on DexScreener](https://example.test/path) injected text)" not in message
