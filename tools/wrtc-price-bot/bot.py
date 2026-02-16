import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
DEXSCREENER_API = f"https://api.dexscreener.com/latest/dex/tokens/{WRTC_MINT}"
ALERT_THRESHOLD = 10.0  # 10% movement

def get_price_data():
    """Fetch price data from DexScreener."""
    try:
        response = requests.get(DEXSCREENER_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pairs = data.get('pairs', [])
        if not pairs:
            return None
            
        # Filter for Raydium pair
        raydium_pair = next((p for p in pairs if p.get('dexId') == 'raydium'), pairs[0])
        
        return {
            'price_usd': float(raydium_pair.get('priceUsd', 0)),
            'price_native': raydium_pair.get('priceNative'),
            'h24_change': raydium_pair.get('priceChange', {}).get('h24', 0),
            'h1_change': raydium_pair.get('priceChange', {}).get('h1', 0),
            'liquidity_usd': raydium_pair.get('liquidity', {}).get('usd', 0),
            'volume_h24': raydium_pair.get('volume', {}).get('h24', 0),
            'url': raydium_pair.get('url')
        }
    except Exception as e:
        logger.error(f"Error fetching price data: {e}")
        return None

def format_price_message(data):
    """Format the price data into a nice Telegram message."""
    return (
        f"💎 *wRTC Price Update*\n\n"
        f"💵 *USD:* `${data['price_usd']:.4f}`\n"
        f"☀️ *SOL:* `{data['price_native']} SOL`\n"
        f"📈 *24h Change:* `{data['h24_change']}%`\n"
        f"⏱ *1h Change:* `{data['h1_change']}%`\n\n"
        f"💧 *Liquidity:* `${data['liquidity_usd']:,.0f}`\n"
        f"📊 *24h Volume:* `${data['volume_h24']:,.0f}`\n\n"
        f"🔗 [View on DexScreener]({data['url']})"
    )

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command."""
    data = get_price_data()
    if not data:
        await update.message.reply_text("❌ Error fetching live price.")
        return
    await update.message.reply_text(format_price_message(data), parse_mode='Markdown', disable_web_page_preview=True)

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to post price every hour to a configured channel."""
    chat_id = os.getenv("PRICE_CHANNEL_ID")
    if not chat_id:
        return
    data = get_price_data()
    if data:
        await context.bot.send_message(chat_id=chat_id, text=format_price_message(data), parse_mode='Markdown', disable_web_page_preview=True)

async def price_alert_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to check for >10% moves in 1 hour."""
    chat_id = os.getenv("PRICE_CHANNEL_ID")
    if not chat_id:
        return
    
    data = get_price_data()
    if not data:
        return

    last_price = context.bot_data.get("last_price")
    current_price = data['price_usd']
    
    if last_price:
        change = ((current_price - last_price) / last_price) * 100
        if abs(change) >= ALERT_THRESHOLD:
            direction = "🚀 MOON" if change > 0 else "📉 DUMP"
            alert_msg = f"⚠️ *wRTC PRICE ALERT*\n\n{direction} detected! Price moved `{change:.2f}%` in the last interval.\n\n" + format_price_message(data)
            await context.bot.send_message(chat_id=chat_id, text=alert_msg, parse_mode='Markdown', disable_web_page_preview=True)
    
    context.bot_data["last_price"] = current_price

def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found.")
        return

    application = ApplicationBuilder().token(token).build()
    
    # Handlers
    application.add_handler(CommandHandler("price", price_cmd))
    
    # Jobs
    job_queue = application.job_queue
    # Auto-post every hour
    job_queue.run_repeating(auto_post_job, interval=3600, first=10)
    # Check alerts every 5 minutes
    job_queue.run_repeating(price_alert_job, interval=300, first=15)
    
    logger.info("wRTC Price Bot starting with polling loop...")
    application.run_polling()

if __name__ == '__main__':
    main()
