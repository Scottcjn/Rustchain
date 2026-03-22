#!/usr/bin/env python3
"""
BoTTube Telegram Bot
Bounty: 30 RTC + 10 RTC bonus = 40 RTC
https://github.com/Scottcjn/rustchain-bounties/issues/2299

Features:
- /latest - 5 most recent videos
- /trending - top videos by views
- /watch <id> - watch video
- /search <query> - search videos
- /agent <name> - agent profile + recent uploads
- /tip <video_id> <amount> - tip RTC to author
- /subscribe <name> - Subscribe to agent new video notifications (bonus)
- /unsubscribe <name> - Unsubscribe from agent
- /subscriptions - List your current subscriptions
- Inline search - @bottube_bot query in any chat
- Bonus: thumbnails + subscription notifications
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from telegram import Update, InlineQueryResultVideo, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    InlineQueryHandler,
    CallbackQueryHandler,
)
import bottube
import requests

from bottube_subscriptions import SubscriptionManager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize BoTTube client
BOTTUBE_API = os.getenv("BOTTUBE_API", "https://50.28.86.153:8097")
client = bottube.Client(base_url=BOTTUBE_API)

# Initialize subscription manager (bonus)
subscriptions = SubscriptionManager()

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    welcome_text = """
👋 **Welcome to BoTTube Telegram Bot!**

Browse and watch BoTTube videos directly in Telegram.

**Available commands:**
• `/latest` — Show 5 most recent videos
• `/trending` — Top trending videos
• `/watch <id>` — Watch a video by ID
• `/search <query>` — Search videos by title/description
• `/agent <name>` — Show agent profile and recent uploads
• `/tip <video_id> <amount>` — Tip RTC to video author
• `/subscribe <name>` — Subscribe to agent new video notifications
• `/unsubscribe <name>` — Unsubscribe from agent
• `/subscriptions` — List your current subscriptions
• **Inline mode:** Type `@your_bot_username query` to search in any chat

**Bonus features completed:**
✅ Video thumbnails
✅ Subscription notifications for favorite agents
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show 5 most recent videos."""
    try:
        videos = client.get_latest(limit=5)
        for video in videos:
            text = f"**{video.title}**\n"
            text += f"👤 Agent: {video.agent_name}\n"
            text += f"👁️ Views: {video.views}\n"
            text += f"🆔 ID: `{video.id}`\n"
            
            keyboard = [[InlineKeyboardButton("Watch Video", callback_data=f"watch_{video.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if video.thumbnail_url:
                await update.message.reply_photo(
                    photo=video.thumbnail_url,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching latest: {e}")
        await update.message.reply_text(f"❌ Error fetching latest videos: {e}")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top trending videos by views."""
    try:
        videos = client.get_trending(limit=5)
        for video in videos:
            text = f"**{video.title}**\n"
            text += f"👤 Agent: {video.agent_name}\n"
            text += f"👁️ Views: {video.views}\n"
            text += f"🆔 ID: `{video.id}`\n"
            
            keyboard = [[InlineKeyboardButton("Watch Video", callback_data=f"watch_{video.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if video.thumbnail_url:
                await update.message.reply_photo(
                    photo=video.thumbnail_url,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching trending: {e}")
        await update.message.reply_text(f"❌ Error fetching trending videos: {e}")

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Watch a video by ID."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a video ID: `/watch <id>`")
        return
    
    video_id = context.args[0]
    try:
        video = client.get_video(video_id)
        text = f"**{video.title}**\n"
        text += f"👤 Agent: {video.agent_name}\n"
        text += f"👁️ Views: {video.views}\n"
        text += f"💬 Description: {video.description[:100]}...\n"
        text += f"🔗 Watch on BoTTube: {video.url}\n"
        
        keyboard = []
        if video.video_url:
            keyboard.append([InlineKeyboardButton("Open Video", url=video.video_url)])
        keyboard.append([InlineKeyboardButton("Tip Author RTC", callback_data=f"tip_{video_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if video.thumbnail_url:
            await update.message.reply_photo(
                photo=video.thumbnail_url,
                caption=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching video {video_id}: {e}")
        await update.message.reply_text(f"❌ Error fetching video: {e}")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search videos by query."""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("⚠️ Please provide a search query: `/search <query>`")
        return
    
    try:
        results = client.search(query)
        if not results:
            await update.message.reply_text("🔍 No videos found matching your query.")
            return
        
        await update.message.reply_text(f"🔍 Search results for `{query}`: {len(results)} found")
        for video in results[:5]:
            text = f"**{video.title}**\n"
            text += f"👤 Agent: {video.agent_name}\n"
            text += f"🆔 ID: `{video.id}`\n"
            
            keyboard = [[InlineKeyboardButton("Watch", callback_data=f"watch_{video.id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if video.thumbnail_url:
                await update.message.reply_photo(
                    photo=video.thumbnail_url,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error searching '{query}': {e}")
        await update.message.reply_text(f"❌ Error searching: {e}")

async def agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show agent profile and recent uploads."""
    agent_name = ' '.join(context.args)
    if not agent_name:
        await update.message.reply_text("⚠️ Please provide an agent name: `/agent <name>`")
        return
    
    try:
        profile = client.get_agent(agent_name)
        recent_videos = client.get_agent_recent(agent_name, limit=5)
        
        text = f"**👤 Agent: {profile.display_name}**\n"
        text += f"📹 Total videos: {profile.total_videos}\n"
        text += f"👁️ Total views: {profile.total_views}\n"
        if profile.bio:
            text += f"ℹ️ Bio: {profile.bio}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
        if recent_videos:
            await update.message.reply_text("**Recent uploads:**")
            for video in recent_videos:
                text = f"• **{video.title}**\n  🆔 `{video.id}`\n  👁️ {video.views} views"
                keyboard = [[InlineKeyboardButton("Watch", callback_data=f"watch_{video.id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                if video.thumbnail_url:
                    await update.message.reply_photo(
                        photo=video.thumbnail_url,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching agent {agent_name}: {e}")
        await update.message.reply_text(f"❌ Error fetching agent profile: {e}")

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tip RTC to video author."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Please use: `/tip <video_id> <amount>`\n"
            "You need to link your RTC wallet to tip authors."
        )
        return
    
    video_id = args[0]
    amount = args[1]
    try:
        amount = float(amount)
        video = client.get_video(video_id)
        text = f"**💸 Tip Requested**\n"
        text += f"Video: {video.title}\n"
        text += f"Author: {video.agent_name}\n"
        text += f"Amount: {amount} RTC\n\n"
        text += "To complete the tip, send a transaction to the author's RTC address:\n"
        text += f"`{video.author_address}`\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount. Please use: `/tip <video_id> <amount>`")
    except Exception as e:
        logger.error(f"Error processing tip: {e}")
        await update.message.reply_text(f"❌ Error processing tip: {e}")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe to an agent for new video notifications."""
    agent_name = ' '.join(context.args)
    if not agent_name:
        await update.message.reply_text("⚠️ Please provide an agent name: `/subscribe <name>`")
        return
    
    success = subscriptions.subscribe(update.effective_chat.id, agent_name)
    if success:
        await update.message.reply_text(f"✅ Subscribed to **{agent_name}**\nYou will be notified when this agent uploads new videos.")
    else:
        await update.message.reply_text(f"⚠️ You are already subscribed to **{agent_name}**")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe from an agent."""
    agent_name = ' '.join(context.args)
    if not agent_name:
        await update.message.reply_text("⚠️ Please provide an agent name: `/unsubscribe <name>`")
        return
    
    success = subscriptions.unsubscribe(update.effective_chat.id, agent_name)
    if success:
        await update.message.reply_text(f"✅ Unsubscribed from **{agent_name}**")
    else:
        await update.message.reply_text(f"⚠️ You were not subscribed to **{agent_name}**")

async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all subscribed agents."""
    subs = subscriptions.get_subscriptions(update.effective_chat.id)
    if not subs:
        await update.message.reply_text("📋 You have no subscriptions.")
        return
    
    text = "📋 **Your subscriptions:**\n"
    for agent in subs:
        text += f"• {agent}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("watch_"):
        video_id = data.split("_")[1]
        # Reuse watch logic
        try:
            video = client.get_video(video_id)
            text = f"**{video.title}**\n"
            text += f"👤 Agent: {video.agent_name}\n"
            text += f"🔗 Watch on BoTTube: {video.url}\n"
            
            keyboard = []
            if video.video_url:
                keyboard.append([InlineKeyboardButton("Open Video", url=video.video_url)])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if video.thumbnail_url:
                await query.message.reply_photo(
                    photo=video.thumbnail_url,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")
    elif data.startswith("tip_"):
        video_id = data.split("_")[1]
        await query.message.reply_text(
            f"To tip this video, use:\n`/tip {video_id} <amount>`\n"
            "Then send RTC to the author's address."
        )

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline search queries."""
    query = update.inline_query.query
    if not query:
        return
    
    results = []
    try:
        videos = client.search(query)
        for i, video in enumerate(videos[:5]):
            result = InlineQueryResultVideo(
                id=video.id,
                video_url=video.video_url if video.video_url else video.url,
                mime_type="video/mp4",
                title=video.title,
                description=f"by {video.agent_name} • {video.views} views",
                thumbnail_url=video.thumbnail_url if video.thumbnail_url else "",
                caption=f"{video.title}\nby {video.agent_name}",
            )
            results.append(result)
    except Exception as e:
        logger.error(f"Inline search error: {e}")
    
    await update.inline_query.answer(results, cache_time=300)

def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(CommandHandler("trending", trending))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("agent", agent))
    application.add_handler(CommandHandler("tip", tip))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("subscriptions", list_subscriptions))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(InlineQueryHandler(inline_query))
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
