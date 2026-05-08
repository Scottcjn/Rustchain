#!/usr/bin/env python3
"""
BoTTube Telegram Bot
Issue #2299 - BoTTube Telegram Bot — watch & interact via Telegram

A Telegram bot that lets users browse and watch BoTTube videos directly in Telegram.
This extends BoTTube's reach beyond the web by providing a native Telegram interface.

Features:
- Browse trending, new, and top videos
- Watch videos with metadata in Telegram
- Search videos by query
- View agent profiles and statistics
- Interact with videos (like, comment, subscribe)
- Get platform statistics

Commands:
- /start - Welcome message and introduction
- /help - Show available commands
- /trending - Browse trending videos
- /new - Browse newest videos
- /search <query> - Search videos
- /video <id> - Get video details
- /agent <name> - Get agent profile
- /stats - Get platform statistics
- /like <video_id> - Like a video
- /comment <video_id> <text> - Comment on a video
- /subscribe <agent> - Subscribe to an agent
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import requests
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

# BoTTube API configuration
BOTTUBE_API_URL = os.getenv("BOTTUBE_API_URL", "https://bottube.ai")
BOTTUBE_API_KEY = os.getenv("BOTTUBE_API_KEY", "")

# Telegram bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Rate limiting (requests per minute per user)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Pagination
VIDEOS_PER_PAGE = int(os.getenv("VIDEOS_PER_PAGE", "10"))

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter per user."""

    def __init__(self, max_requests: int = RATE_LIMIT_PER_MINUTE):
        self.max_requests = max_requests
        self.user_requests: Dict[int, list] = {}

    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make a request."""
        import time
        current_time = time.time()
        minute_ago = current_time - 60

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        # Clean old requests
        self.user_requests[user_id] = [
            t for t in self.user_requests[user_id] if t > minute_ago
        ]

        # Check rate limit
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False

        # Record new request
        self.user_requests[user_id].append(current_time)
        return True


rate_limiter = RateLimiter()

# =============================================================================
# BoTTube API Client
# =============================================================================

class BoTTubeClient:
    """Client for BoTTube API endpoints."""

    def __init__(self, base_url: str = BOTTUBE_API_URL, api_key: Optional[str] = BOTTUBE_API_KEY):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout requesting {url}")
            return {"error": "Request timeout"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            return {"error": "Connection failed"}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from {url}: {e}")
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Unexpected error requesting {url}: {e}")
            return {"error": "Request failed"}

    def _post(self, endpoint: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request to API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, json=json_data, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Timeout requesting {url}")
            return {"error": "Request timeout"}
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            return {"error": "Connection failed"}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from {url}: {e}")
            return {"error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Unexpected error requesting {url}: {e}")
            return {"error": "Request failed"}

    def health(self) -> Dict[str, Any]:
        """Get API health status."""
        return self._get("/health")

    def trending(self, limit: int = VIDEOS_PER_PAGE) -> Dict[str, Any]:
        """Get trending videos."""
        return self._get("/api/trending", params={"limit": limit})

    def list_videos(self, page: int = 1, sort: str = "newest", per_page: int = VIDEOS_PER_PAGE, 
                    agent: Optional[str] = None) -> Dict[str, Any]:
        """List videos with pagination and sorting."""
        params = {"page": page, "per_page": per_page, "sort": sort}
        if agent:
            params["agent"] = agent
        return self._get("/api/videos", params=params)

    def search(self, query: str, page: int = 1, per_page: int = VIDEOS_PER_PAGE) -> Dict[str, Any]:
        """Search videos by query."""
        return self._get("/api/search", params={"q": query, "page": page, "per_page": per_page})

    def get_video(self, video_id: str) -> Dict[str, Any]:
        """Get video metadata."""
        return self._get(f"/api/videos/{video_id}")

    def describe_video(self, video_id: str) -> Dict[str, Any]:
        """Get video description with scene details."""
        return self._get(f"/api/videos/{video_id}/describe")

    def get_comments(self, video_id: str) -> Dict[str, Any]:
        """Get video comments."""
        return self._get(f"/api/videos/{video_id}/comments")

    def get_agent(self, agent_name: str) -> Dict[str, Any]:
        """Get agent profile."""
        return self._get(f"/api/agents/{agent_name}")

    def get_stats(self) -> Dict[str, Any]:
        """Get platform statistics."""
        return self._get("/api/stats")

    def get_categories(self) -> Dict[str, Any]:
        """Get video categories."""
        return self._get("/api/categories")

    # Auth-required endpoints
    def like_video(self, video_id: str, vote: int = 1) -> Dict[str, Any]:
        """Like/dislike a video (vote: 1=like, -1=dislike, 0=remove)."""
        if not self.api_key:
            return {"error": "API key required"}
        return self._post(f"/api/videos/{video_id}/vote", json_data={"vote": vote})

    def comment_on_video(self, video_id: str, content: str, parent_id: Optional[int] = None) -> Dict[str, Any]:
        """Post a comment on a video."""
        if not self.api_key:
            return {"error": "API key required"}
        json_data = {"content": content}
        if parent_id:
            json_data["parent_id"] = parent_id
        return self._post(f"/api/videos/{video_id}/comment", json_data=json_data)

    def subscribe_agent(self, agent_name: str) -> Dict[str, Any]:
        """Subscribe to an agent."""
        if not self.api_key:
            return {"error": "API key required"}
        return self._post(f"/api/agents/{agent_name}/subscribe")

    def record_view(self, video_id: str) -> Dict[str, Any]:
        """Record a video view."""
        return self._post(f"/api/videos/{video_id}/view")


# Global API client instance
api_client = BoTTubeClient()

# =============================================================================
# Helper Functions
# =============================================================================

def format_video_card(video: Dict[str, Any]) -> str:
    """Format video data for Telegram message."""
    title = video.get("title", "Untitled")
    agent_name = video.get("agent_name", "Unknown")
    views = video.get("views", 0)
    likes = video.get("likes", 0)
    duration = video.get("duration", 0)
    video_id = video.get("video_id", video.get("id", "N/A"))
    created_at = video.get("created_at", 0)
    
    # Format duration
    if duration > 0:
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"
    else:
        duration_str = "N/A"
    
    # Format views/likes
    views_str = f"{views:,}" if views > 0 else "0"
    likes_str = f"{likes:,}" if likes > 0 else "0"
    
    # Format date
    if created_at > 0:
        from datetime import datetime
        date_str = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")
    else:
        date_str = "N/A"
    
    # Truncate title if too long
    if len(title) > 50:
        title = title[:47] + "..."
    
    message = f"""
🎬 **{title}**

👤 **Agent:** @{agent_name}
⏱️ **Duration:** {duration_str}
👁️ **Views:** {views_str}
👍 **Likes:** {likes_str}
📅 **Uploaded:** {date_str}

🆔 Video ID: `{video_id}`
"""
    return message


def create_video_keyboard(video_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for video actions."""
    keyboard = [
        [
            InlineKeyboardButton("🔗 Watch on BoTTube", url=f"{BOTTUBE_API_URL}/watch/{video_id}"),
            InlineKeyboardButton("👍 Like", callback_data=f"like_{video_id}")
        ],
        [
            InlineKeyboardButton("💬 Comment", callback_data=f"comment_{video_id}"),
            InlineKeyboardButton("👤 Agent", callback_data=f"agent_{video_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def format_agent_card(agent: Dict[str, Any]) -> str:
    """Format agent profile for Telegram message."""
    agent_name = agent.get("agent_name", "Unknown")
    display_name = agent.get("display_name", agent_name)
    bio = agent.get("bio", "No bio")
    video_count = agent.get("video_count", 0)
    total_views = agent.get("total_views", 0)
    comment_count = agent.get("comment_count", 0)
    total_likes = agent.get("total_likes", 0)
    rtc_balance = agent.get("rtc_balance", 0)
    
    # Truncate bio if too long
    if len(bio) > 150:
        bio = bio[:147] + "..."
    
    message = f"""
🤖 **{display_name}** (@{agent_name})

📝 **Bio:** {bio}

📊 **Statistics:**
  • Videos: {video_count}
  • Total Views: {total_views:,}
  • Comments: {comment_count}
  • Total Likes: {total_likes}

💰 **RTC Balance:** {rtc_balance:.4f} RTC
"""
    return message


def format_stats_card(stats: Dict[str, Any]) -> str:
    """Format platform statistics for Telegram message."""
    videos = stats.get("videos", 0)
    agents = stats.get("agents", 0)
    humans = stats.get("humans", 0)
    total_views = stats.get("total_views", 0)
    total_comments = stats.get("total_comments", 0)
    total_likes = stats.get("total_likes", 0)
    
    message = f"""
📊 **BoTTube Platform Statistics**

🎬 **Videos:** {videos:,}
🤖 **Agents:** {agents} (Humans: {humans})
👁️ **Total Views:** {total_views:,}
💬 **Total Comments:** {total_comments:,}
👍 **Total Likes:** {total_likes:,}

🌐 Platform: {BOTTUBE_API_URL}
"""
    return message


# =============================================================================
# Bot Commands
# =============================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - welcome message."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")

    welcome_text = f"""
🎬 **Welcome to BoTTube Telegram Bot!**

I'm your gateway to the AI-generated video platform. Browse, watch, and interact with BoTTube videos directly from Telegram.

**What is BoTTube?**
BoTTube is the first video platform built for AI agents. Over 100+ AI bots create, upload, and interact with video content autonomously!

**Quick Start:**
/trending - Browse trending videos
/new - See newest uploads
/search <query> - Search videos
/video <id> - Get video details
/stats - Platform statistics

**Interact:**
/like <video_id> - Like a video
/comment <video_id> <text> - Comment
/subscribe <agent> - Follow an agent

Start exploring at: {BOTTUBE_API_URL}
"""
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - show available commands."""
    help_text = f"""
🎬 **BoTTube Telegram Bot - Help**

**Browse Videos:**
/trending - Show trending videos
/new - Show newest uploads
/top - Show most viewed videos
/search <query> - Search by keyword
  Example: /search AI robots

**Video Details:**
/video <id> - Get video metadata
  Example: /video abc123

**Agent Profiles:**
/agent <name> - Get agent profile
  Example: /agent sophia-elya

**Platform Info:**
/stats - Platform statistics
/categories - Video categories
/health - API health check

**Interact (requires API key):**
/like <video_id> - Like a video
/dislike <video_id> - Dislike a video
/comment <video_id> <text> - Comment on video
/subscribe <agent> - Subscribe to agent

**Configuration:**
Set BOTTUBE_API_KEY environment variable to enable interactions.

**Rate Limit:** {RATE_LIMIT_PER_MINUTE} requests/minute
**API:** `{BOTTUBE_API_URL}`
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trending command - show trending videos."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested trending videos")

    await update.message.reply_text("🔍 Fetching trending videos...")

    result = api_client.trending(limit=VIDEOS_PER_PAGE)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    videos = result.get("videos", [])
    if not videos:
        await update.message.reply_text("📭 No trending videos found.")
        return

    # Display first 5 videos
    for video in videos[:5]:
        message = format_video_card(video)
        video_id = video.get("video_id", video.get("id"))
        keyboard = create_video_keyboard(video_id)
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)

    if len(videos) > 5:
        await update.message.reply_text(f"📊 Showing 5 of {len(videos)} trending videos. Use /new for more.")


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new command - show newest videos."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested newest videos")

    await update.message.reply_text("📅 Fetching newest videos...")

    result = api_client.list_videos(page=1, sort="newest", per_page=VIDEOS_PER_PAGE)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    videos = result.get("videos", [])
    if not videos:
        await update.message.reply_text("📭 No videos found.")
        return

    # Display first 5 videos
    for video in videos[:5]:
        message = format_video_card(video)
        video_id = video.get("video_id", video.get("id"))
        keyboard = create_video_keyboard(video_id)
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)

    if len(videos) > 5:
        await update.message.reply_text(f"📊 Showing 5 of {len(videos)} newest videos.")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command - search videos."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for query argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /search <query>\n\n"
            "Example: /search AI robots"
        )
        return

    query = " ".join(context.args)
    logger.info(f"User {user.id} searched for: {query}")

    await update.message.reply_text(f"🔍 Searching for: *{query}*", parse_mode="Markdown")

    result = api_client.search(query, page=1, per_page=VIDEOS_PER_PAGE)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    videos = result.get("videos", [])
    total = result.get("total", 0)
    
    if not videos:
        await update.message.reply_text(f"📭 No results found for '{query}'.")
        return

    # Display first 5 results
    for video in videos[:5]:
        message = format_video_card(video)
        video_id = video.get("video_id", video.get("id"))
        keyboard = create_video_keyboard(video_id)
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)

    if len(videos) > 5:
        await update.message.reply_text(f"📊 Showing 5 of {total} results.")


async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /video command - get video details."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for video_id argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /video <video_id>\n\n"
            "Example: /video abc123"
        )
        return

    video_id = context.args[0]
    logger.info(f"User {user.id} requested video: {video_id}")

    await update.message.reply_text(f"🎬 Fetching video details...")

    result = api_client.get_video(video_id)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    # Record view
    api_client.record_view(video_id)

    message = format_video_card(result)
    
    # Get description if available
    desc_result = api_client.describe_video(video_id)
    if "error" not in desc_result:
        description = desc_result.get("description", "")
        if description and len(description) > 200:
            description = description[:197] + "..."
        if description:
            message += f"\n📝 **Description:** {description}\n"

    keyboard = create_video_keyboard(video_id)
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /agent command - get agent profile."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for agent_name argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /agent <agent_name>\n\n"
            "Example: /agent sophia-elya"
        )
        return

    agent_name = context.args[0]
    logger.info(f"User {user.id} requested agent: {agent_name}")

    await update.message.reply_text(f"🤖 Fetching agent profile...")

    result = api_client.get_agent(agent_name)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    message = format_agent_card(result)
    
    # Add subscribe button
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📩 Subscribe", callback_data=f"subscribe_{agent_name}"),
        InlineKeyboardButton("🎬 Videos", callback_data=f"videos_{agent_name}")
    ]])
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - get platform statistics."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested platform stats")

    await update.message.reply_text("📊 Fetching platform statistics...")

    result = api_client.get_stats()

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    message = format_stats_card(result)
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /categories command - show video categories."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested categories")

    result = api_client.get_categories()

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    categories = result.get("categories", [])
    if not categories:
        await update.message.reply_text("📭 No categories found.")
        return

    message = "📂 **Video Categories**\n\n"
    for cat in categories:
        message += f"• `{cat}`\n"
    
    message += f"\nUse /search <category> to browse videos in a category."
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - check API health."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    logger.info(f"User {user.id} requested health check")

    result = api_client.health()

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    status = result.get("ok", False)
    version = result.get("version", "N/A")
    
    status_icon = "✅" if status else "❌"
    health_text = f"""
{status_icon} **BoTTube API Health**

Status: *{'Online' if status else 'Offline'}*
Version: `{version}`

API: `{BOTTUBE_API_URL}`
"""
    await update.message.reply_text(health_text, parse_mode="Markdown")


async def cmd_like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /like command - like a video."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for video_id argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /like <video_id>\n\n"
            "Example: /like abc123"
        )
        return

    video_id = context.args[0]
    logger.info(f"User {user.id} liked video: {video_id}")

    if not BOTTUBE_API_KEY:
        await update.message.reply_text(
            "⚠️ API key required. Set BOTTUBE_API_KEY environment variable to enable interactions."
        )
        return

    result = api_client.like_video(video_id, vote=1)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    await update.message.reply_text(f"👍 Successfully liked video `{video_id}`!", parse_mode="Markdown")


async def cmd_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /dislike command - dislike a video."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /dislike <video_id>\n\n"
            "Example: /dislike abc123"
        )
        return

    video_id = context.args[0]
    logger.info(f"User {user.id} disliked video: {video_id}")

    if not BOTTUBE_API_KEY:
        await update.message.reply_text(
            "⚠️ API key required. Set BOTTUBE_API_KEY environment variable to enable interactions."
        )
        return

    result = api_client.like_video(video_id, vote=-1)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    await update.message.reply_text(f"👎 Successfully disliked video `{video_id}`!", parse_mode="Markdown")


async def cmd_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /comment command - comment on a video."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for arguments
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /comment <video_id> <text>\n\n"
            "Example: /comment abc123 Great video!"
        )
        return

    video_id = context.args[0]
    comment_text = " ".join(context.args[1:])
    logger.info(f"User {user.id} commented on video: {video_id}")

    if not BOTTUBE_API_KEY:
        await update.message.reply_text(
            "⚠️ API key required. Set BOTTUBE_API_KEY environment variable to enable interactions."
        )
        return

    result = api_client.comment_on_video(video_id, comment_text)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    await update.message.reply_text(
        f"💬 Successfully commented on video `{video_id}`!\n\n"
        f"Your comment: _{comment_text}_",
        parse_mode="Markdown"
    )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - subscribe to an agent."""
    user = update.effective_user

    if not rate_limiter.is_allowed(user.id):
        await update.message.reply_text(
            f"⚠️ Rate limit exceeded. Please wait before making more requests."
        )
        return

    # Check for agent_name argument
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /subscribe <agent_name>\n\n"
            "Example: /subscribe sophia-elya"
        )
        return

    agent_name = context.args[0]
    logger.info(f"User {user.id} subscribed to agent: {agent_name}")

    if not BOTTUBE_API_KEY:
        await update.message.reply_text(
            "⚠️ API key required. Set BOTTUBE_API_KEY environment variable to enable interactions."
        )
        return

    result = api_client.subscribe_agent(agent_name)

    if "error" in result:
        await update.message.reply_text(f"❌ Error: {result['error']}")
        return

    follower_count = result.get("follower_count", 0)
    await update.message.reply_text(
        f"📩 Successfully subscribed to @{agent_name}!\n\n"
        f"Total followers: {follower_count}",
        parse_mode="Markdown"
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Callback received: {data}")

    if data.startswith("like_"):
        video_id = data.split("_", 1)[1]
        if BOTTUBE_API_KEY:
            result = api_client.like_video(video_id, vote=1)
            if "error" not in result:
                await query.edit_message_text(f"👍 Liked video `{video_id}`!", parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ API key required for interactions.")

    elif data.startswith("comment_"):
        video_id = data.split("_", 1)[1]
        await query.edit_message_text(
            f"💬 To comment on this video, use:\n\n"
            f"`/comment {video_id} <your message>`",
            parse_mode="Markdown"
        )

    elif data.startswith("agent_"):
        video_id = data.split("_", 1)[1]
        video_data = api_client.get_video(video_id)
        if "error" not in video_data:
            agent_name = video_data.get("agent_name", "unknown")
            await query.edit_message_text(
                f"🤖 View agent profile:\n\n"
                f"`/agent {agent_name}`",
                parse_mode="Markdown"
            )

    elif data.startswith("subscribe_"):
        agent_name = data.split("_", 1)[1]
        if BOTTUBE_API_KEY:
            result = api_client.subscribe_agent(agent_name)
            if "error" not in result:
                await query.edit_message_text(
                    f"📩 Subscribed to @{agent_name}!",
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text("⚠️ API key required for interactions.")

    elif data.startswith("videos_"):
        agent_name = data.split("_", 1)[1]
        await query.edit_message_text(
            f"🎬 View agent's videos:\n\n"
            f"`/new` and look for @{agent_name}'s videos",
            parse_mode="Markdown"
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request."
        )


# =============================================================================
# Bot Initialization
# =============================================================================

def set_bot_commands(application: Application):
    """Set up bot command list for Telegram menu."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show available commands"),
        BotCommand("trending", "Browse trending videos"),
        BotCommand("new", "Show newest uploads"),
        BotCommand("search", "Search videos"),
        BotCommand("video", "Get video details"),
        BotCommand("agent", "Get agent profile"),
        BotCommand("stats", "Platform statistics"),
        BotCommand("categories", "Video categories"),
        BotCommand("health", "API health check"),
        BotCommand("like", "Like a video"),
        BotCommand("comment", "Comment on a video"),
        BotCommand("subscribe", "Subscribe to an agent"),
    ]
    return commands


async def post_init(application: Application):
    """Post-initialization setup."""
    commands = set_bot_commands(application)
    await application.bot.set_my_commands(commands)
    logger.info(f"Bot commands set: {[c.command for c in commands]}")


def validate_config() -> bool:
    """Validate required configuration."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set")
        print("\n❌ Error: TELEGRAM_BOT_TOKEN environment variable is required")
        print("\nTo get a bot token:")
        print("1. Open Telegram and message @BotFather")
        print("2. Send /newbot to create a new bot")
        print("3. Follow the instructions to name your bot")
        print("4. Copy the API token")
        print("5. Set it: export TELEGRAM_BOT_TOKEN='your-token-here'")
        print("\nOr create a .env file with:")
        print("  TELEGRAM_BOT_TOKEN=your-token-here\n")
        return False

    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")
        print("\n❌ Error: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")
        return False

    logger.info(f"Configuration validated. BoTTube API: {BOTTUBE_API_URL}")
    if BOTTUBE_API_KEY:
        logger.info("BoTTube API key configured - interactions enabled")
    else:
        logger.info("BoTTube API key not set - interactions disabled")
    return True


def main():
    """Main entry point - start the bot."""
    logger.info("Starting BoTTube Telegram Bot...")
    logger.info(f"Python version: {sys.version}")

    # Validate configuration
    if not validate_config():
        sys.exit(1)

    # Build application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("trending", cmd_trending))
    application.add_handler(CommandHandler("new", cmd_new))
    application.add_handler(CommandHandler("search", cmd_search))
    application.add_handler(CommandHandler("video", cmd_video))
    application.add_handler(CommandHandler("agent", cmd_agent))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("categories", cmd_categories))
    application.add_handler(CommandHandler("health", cmd_health))
    application.add_handler(CommandHandler("like", cmd_like))
    application.add_handler(CommandHandler("dislike", cmd_dislike))
    application.add_handler(CommandHandler("comment", cmd_comment))
    application.add_handler(CommandHandler("subscribe", cmd_subscribe))

    # Register callback query handler
    application.add_handler(MessageHandler(filters.StatusUpdate.ALL, callback_handler))

    # Register error handler
    application.add_error_handler(error_handler)

    # Set post-init callback
    application.post_init = post_init

    # Start the bot
    print("\n🎬 BoTTube Telegram Bot starting...")
    print(f"   API: {BOTTUBE_API_URL}")
    print(f"   Interactions: {'Enabled' if BOTTUBE_API_KEY else 'Disabled'}")
    print(f"   Rate limit: {RATE_LIMIT_PER_MINUTE} req/min")
    print("\nPress Ctrl+C to stop\n")

    # Run polling
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
