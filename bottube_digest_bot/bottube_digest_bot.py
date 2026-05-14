#!/usr/bin/env python3
"""
BoTTube Weekly Digest Bot

Issue #2279 - Automated community newsletter bot that sends weekly digests
containing top videos, miner highlights, epoch summaries, and community updates.

Supports multiple delivery channels:
- Discord (webhook or bot)
- Telegram
- Email (SMTP)

Features:
- Weekly scheduled digest generation
- Top N miners by balance
- Top videos from BoTTube
- Epoch summary and rewards
- Network statistics
- Configurable delivery channels
"""

import argparse
import asyncio
import json
import logging
import smtplib
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import httpx

from config import BotConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("bottube-digest-bot")


@dataclass
class DigestContent:
    """Structured digest content."""

    # Metadata
    generated_at: str = ""
    period_start: str = ""
    period_end: str = ""

    # Network stats
    current_epoch: int = 0
    current_slot: int = 0
    block_height: int = 0
    active_miners: int = 0
    node_version: str = ""
    node_uptime: str = ""

    # Top miners
    top_miners: List[Dict[str, Any]] = field(default_factory=list)

    # Top videos
    top_videos: List[Dict[str, Any]] = field(default_factory=list)

    # Epoch rewards (optional)
    epoch_rewards: List[Dict[str, Any]] = field(default_factory=list)

    # Additional stats
    total_rtc_supply: float = 0.0
    network_hashrate: str = "N/A"

    # Raw data for custom formatting
    raw_data: Dict[str, Any] = field(default_factory=dict)


class RustChainClient:
    """Client for RustChain API endpoints."""

    def __init__(self, config: BotConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.api_timeout),
            verify=config.verify_ssl,
            headers={"User-Agent": "bottube-digest-bot/1.0"},
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_json(self, endpoint: str) -> Dict[str, Any]:
        """Fetch JSON from an API endpoint."""
        url = f"{self.config.rustchain_node_url}{endpoint}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"API request failed for {endpoint}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {endpoint}: {e}")
            return {}

    async def health(self) -> Dict[str, Any]:
        """Get node health status."""
        return await self.get_json("/health")

    async def epoch(self) -> Dict[str, Any]:
        """Get current epoch information."""
        return await self.get_json("/epoch")

    async def miners(self) -> List[Dict[str, Any]]:
        """Get list of active miners."""
        return await self.get_json("/api/miners")

    async def wallet_balance(self, miner_id: str) -> Dict[str, Any]:
        """Get balance for a specific miner."""
        return await self.get_json(f"/wallet/balance?miner_id={miner_id}")

    async def rewards_epoch(self, epoch: int) -> Dict[str, Any]:
        """Get rewards for a specific epoch."""
        return await self.get_json(f"/rewards/epoch/{epoch}")


class BoTTubeClient:
    """Client for BoTTube API endpoints."""

    def __init__(self, config: BotConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.bottube_api_timeout),
            headers={"User-Agent": "bottube-digest-bot/1.0"},
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_json(self, endpoint: str) -> Dict[str, Any]:
        """Fetch JSON from BoTTube API."""
        url = f"{self.config.bottube_url}{endpoint}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"BoTTube API request failed for {endpoint}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {endpoint}: {e}")
            return {}

    async def videos(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent videos from BoTTube."""
        result = await self.get_json(f"/api/feed?limit={limit}")
        return result.get("items", []) if isinstance(result, dict) else []


class DigestGenerator:
    """Generates weekly digest content from RustChain and BoTTube APIs."""

    def __init__(self, config: BotConfig):
        self.config = config
        self.rustchain_client = RustChainClient(config)
        self.bottube_client = BoTTubeClient(config)

    async def close(self):
        """Close HTTP clients."""
        await self.rustchain_client.close()
        await self.bottube_client.close()

    async def generate(self) -> DigestContent:
        """Generate complete digest content."""
        logger.info("Generating weekly digest content...")

        content = DigestContent(
            generated_at=datetime.now(timezone.utc).isoformat(),
            period_start=self._get_period_start(),
            period_end=datetime.now(timezone.utc).isoformat(),
        )

        # Fetch network data in parallel
        health_data, epoch_data, miners_data, videos_data = await self._fetch_all_data()

        # Process health data
        content.node_version = health_data.get("version", "unknown")
        uptime_s = health_data.get("uptime_s", 0)
        content.node_uptime = self._format_uptime(uptime_s)

        # Process epoch data
        content.current_epoch = epoch_data.get("epoch", 0)
        content.current_slot = epoch_data.get("slot", 0)
        content.block_height = epoch_data.get("height", 0)

        # Process miners data
        if isinstance(miners_data, list):
            content.active_miners = len(miners_data)
            content.top_miners = await self._get_top_miners(miners_data)

        # Process videos data
        if isinstance(videos_data, list):
            content.top_videos = videos_data[: self.config.digest_top_videos]

        # Store raw data
        content.raw_data = {
            "health": health_data,
            "epoch": epoch_data,
            "miners": miners_data,
            "videos": videos_data,
        }

        logger.info(
            f"Digest generated: epoch {content.current_epoch}, "
            f"{content.active_miners} miners, {len(content.top_videos)} videos"
        )

        return content

    async def _fetch_all_data(self) -> Tuple[Dict, Dict, List, List]:
        """Fetch all data in parallel."""
        health_task = self.rustchain_client.health()
        epoch_task = self.rustchain_client.epoch()
        miners_task = self.rustchain_client.miners()
        videos_task = self.bottube_client.videos(limit=self.config.digest_top_videos * 2)

        results = await asyncio.gather(
            health_task, epoch_task, miners_task, videos_task, return_exceptions=True
        )

        # Handle exceptions gracefully
        health_data = results[0] if not isinstance(results[0], Exception) else {}
        epoch_data = results[1] if not isinstance(results[1], Exception) else {}
        miners_data = results[2] if not isinstance(results[2], Exception) else []
        videos_data = results[3] if not isinstance(results[3], Exception) else []

        return health_data, epoch_data, miners_data, videos_data

    async def _get_top_miners(
        self, miners_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get top N miners by balance."""
        top_n = self.config.digest_top_n
        miners_with_balances = []

        # Fetch balances for all miners (with rate limiting)
        for miner in miners_data[: top_n * 2]:  # Fetch extra to account for failures
            miner_id = miner.get("miner_id", "")
            if not miner_id:
                continue

            balance_data = await self.rustchain_client.wallet_balance(miner_id)
            if balance_data.get("ok", False):
                miners_with_balances.append(
                    {
                        "miner_id": miner_id,
                        "balance_rtc": balance_data.get("amount_rtc", 0.0),
                        "architecture": miner.get("architecture", "unknown"),
                    }
                )

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        # Sort by balance descending
        miners_with_balances.sort(key=lambda x: x["balance_rtc"], reverse=True)

        return miners_with_balances[:top_n]

    def _get_period_start(self) -> str:
        """Get the start of the current digest period."""
        now = datetime.now(timezone.utc)

        if self.config.schedule_mode == "weekly":
            # Go back 7 days
            from datetime import timedelta

            period_start = now - timedelta(days=7)
            return period_start.isoformat()
        else:
            # Daily or custom - go back 1 day
            from datetime import timedelta

            period_start = now - timedelta(days=1)
            return period_start.isoformat()

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in human-readable format."""
        if seconds <= 0:
            return "N/A"

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class DigestFormatter:
    """Formats digest content for different delivery channels."""

    @staticmethod
    def format_discord(content: DigestContent, config: BotConfig) -> str:
        """Format digest for Discord (markdown)."""
        lines = [
            "📊 **BoTTube Weekly Digest**",
            "",
            f"**Period:** {content.period_start[:10]} to {content.period_end[:10]}",
            f"**Generated:** {content.generated_at[:19]} UTC",
            "",
            "━━━ NETWORK STATUS ━━━",
            f"🔗 **Epoch:** {content.current_epoch:,}",
            f"📍 **Slot:** {content.current_slot:,}",
            f"📦 **Height:** {content.block_height:,}",
            f"👥 **Active Miners:** {content.active_miners:,}",
            f"⚙️ **Node Version:** {content.node_version}",
            f"⏱️ **Uptime:** {content.node_uptime}",
            "",
        ]

        if config.include_miner_stats and content.top_miners:
            lines.extend(
                [
                    "━━━ TOP MINERS ━━━",
                ]
            )
            for i, miner in enumerate(content.top_miners, 1):
                miner_id = miner["miner_id"]
                if len(miner_id) > 16:
                    miner_id = miner_id[:16] + "..."
                lines.append(
                    f"{i}. **{miner_id}** - {miner['balance_rtc']:,.2f} RTC "
                    f"({miner['architecture']})"
                )
            lines.append("")

        if config.include_video_highlights and content.top_videos:
            lines.extend(
                [
                    "━━━ TOP VIDEOS ━━━",
                ]
            )
            for i, video in enumerate(content.top_videos, 1):
                title = video.get("title", "Untitled")
                author = video.get("author", {}).get("name", "Unknown")
                lines.append(f"{i}. **{title}** by {author}")
            lines.append("")

        lines.extend(
            [
                "━━━",
                f"_Generated by BoTTube Digest Bot_ | "
                f"[BoTTube](https://bottube.ai) | "
                f"[RustChain](https://rustchain.io)",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def format_telegram(content: DigestContent, config: BotConfig) -> str:
        """Format digest for Telegram (Markdown)."""
        lines = [
            "📊 *BoTTube Weekly Digest*",
            "",
            f"*Period:* {content.period_start[:10]} to {content.period_end[:10]}",
            f"*Generated:* {content.generated_at[:19]} UTC",
            "",
            "*━━━ NETWORK STATUS ━━━*",
            f"🔗 *Epoch:* `{content.current_epoch:,}`",
            f"📍 *Slot:* `{content.current_slot:,}`",
            f"📦 *Height:* `{content.block_height:,}`",
            f"👥 *Active Miners:* `{content.active_miners:,}`",
            f"⚙️ *Node Version:* `{content.node_version}`",
            f"⏱️ *Uptime:* `{content.node_uptime}`",
            "",
        ]

        if config.include_miner_stats and content.top_miners:
            lines.extend(
                [
                    "*━━━ TOP MINERS ━━━*",
                ]
            )
            for i, miner in enumerate(content.top_miners, 1):
                miner_id = miner["miner_id"]
                if len(miner_id) > 16:
                    miner_id = miner_id[:16] + "..."
                lines.append(
                    f"{i}. *{miner_id}* - `{miner['balance_rtc']:,.2f}` RTC "
                    f"({miner['architecture']})"
                )
            lines.append("")

        if config.include_video_highlights and content.top_videos:
            lines.extend(
                [
                    "*━━━ TOP VIDEOS ━━━*",
                ]
            )
            for i, video in enumerate(content.top_videos, 1):
                title = video.get("title", "Untitled")
                author = video.get("author", {}).get("name", "Unknown")
                lines.append(f"{i}. *{title}* by {author}")
            lines.append("")

        lines.extend(
            [
                "*━━━*",
                f"_Generated by BoTTube Digest Bot_ | "
                f"[BoTTube](https://bottube.ai) | "
                f"[RustChain](https://rustchain.io)",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def format_email_html(content: DigestContent, config: BotConfig) -> str:
        """Format digest for email (HTML)."""
        miners_html = ""
        if content.top_miners:
            miners_rows = ""
            for i, miner in enumerate(content.top_miners, 1):
                miners_rows += f"""
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;">{i}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">
                        <code>{miner['miner_id'][:20]}{'...' if len(miner['miner_id']) > 20 else ''}</code>
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd;">
                        <strong>{miner['balance_rtc']:,.2f} RTC</strong>
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{miner['architecture']}</td>
                </tr>
                """
            miners_html = f"""
            <h2 style="color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">
                🏆 Top Miners
            </h2>
            <table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 10px; border: 1px solid #ddd;">#</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Miner ID</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Balance</th>
                    <th style="padding: 10px; border: 1px solid #ddd;">Architecture</th>
                </tr>
                {miners_rows}
            </table>
            """

        videos_html = ""
        if content.top_videos:
            videos_list = ""
            for i, video in enumerate(content.top_videos, 1):
                videos_list += f"""
                <li style="margin: 10px 0;">
                    <strong>{i}. {video.get('title', 'Untitled')}</strong><br>
                    <em>by {video.get('author', {}).get('name', 'Unknown')}</em>
                </li>
                """
            videos_html = f"""
            <h2 style="color: #333; border-bottom: 2px solid #2196F3; padding-bottom: 10px;">
                🎬 Top Videos
            </h2>
            <ol style="line-height: 1.8;">
                {videos_list}
            </ol>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
                .stat-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea; }}
                .stat-card strong {{ display: block; font-size: 24px; color: #667eea; }}
                .stat-card span {{ color: #666; font-size: 14px; }}
                .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 BoTTube Weekly Digest</h1>
                <p>{content.period_start[:10]} to {content.period_end[:10]}</p>
            </div>

            <h2 style="color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px;">
                🌐 Network Status
            </h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <strong>{content.current_epoch:,}</strong>
                    <span>Current Epoch</span>
                </div>
                <div class="stat-card">
                    <strong>{content.current_slot:,}</strong>
                    <span>Slot</span>
                </div>
                <div class="stat-card">
                    <strong>{content.block_height:,}</strong>
                    <span>Block Height</span>
                </div>
                <div class="stat-card">
                    <strong>{content.active_miners:,}</strong>
                    <span>Active Miners</span>
                </div>
                <div class="stat-card">
                    <strong>{content.node_version}</strong>
                    <span>Node Version</span>
                </div>
                <div class="stat-card">
                    <strong>{content.node_uptime}</strong>
                    <span>Node Uptime</span>
                </div>
            </div>

            {miners_html}
            {videos_html}

            <div class="footer">
                <p>Generated by <strong>BoTTube Digest Bot</strong></p>
                <p>
                    <a href="https://bottube.ai" style="color: #667eea;">BoTTube</a> |
                    <a href="https://rustchain.io" style="color: #667eea;">RustChain</a>
                </p>
            </div>
        </body>
        </html>
        """

        return html

    @staticmethod
    def format_email_subject(content: DigestContent) -> str:
        """Generate email subject line."""
        period_end = content.period_end[:10]
        return f"📊 BoTTube Weekly Digest - {period_end}"


class DigestSender:
    """Sends digest content to various delivery channels."""

    def __init__(self, config: BotConfig):
        self.config = config

    async def send_discord_webhook(self, message: str) -> bool:
        """Send digest to Discord via webhook."""
        if not self.config.discord_webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False

        if self.config.dry_run:
            logger.info("[DRY RUN] Would send Discord webhook")
            logger.info(f"Message preview: {message[:200]}...")
            return True

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.discord_webhook_url,
                    json={"content": message},
                    timeout=30.0,
                )
                response.raise_for_status()
                logger.info("Discord webhook sent successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to send Discord webhook: {e}")
            return False

    async def send_discord_bot(self, message: str) -> bool:
        """Send digest to Discord via bot."""
        if not self.config.discord_bot_token or not self.config.discord_channel_id:
            logger.warning("Discord bot token or channel ID not configured")
            return False

        if self.config.dry_run:
            logger.info("[DRY RUN] Would send via Discord bot")
            return True

        try:
            url = (
                f"https://discord.com/api/v10/channels/"
                f"{self.config.discord_channel_id}/messages"
            )
            headers = {"Authorization": f"Bot {self.config.discord_bot_token}"}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"content": message},
                    timeout=30.0,
                )
                response.raise_for_status()
                logger.info("Discord bot message sent successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to send via Discord bot: {e}")
            return False

    async def send_telegram(self, message: str) -> bool:
        """Send digest to Telegram."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            return False

        if self.config.dry_run:
            logger.info("[DRY RUN] Would send Telegram message")
            return True

        try:
            url = (
                f"https://api.telegram.org/bot{self.config.telegram_bot_token}"
                f"/sendMessage"
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": self.config.telegram_chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_email(self, html_content: str, subject: str) -> bool:
        """Send digest via email to all recipients."""
        if not self.config.has_email():
            logger.warning("Email not configured")
            return False

        if self.config.dry_run:
            logger.info(
                f"[DRY RUN] Would send email to {len(self.config.digest_recipients)} recipients"
            )
            return True

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.smtp_from
            msg["To"] = ", ".join(self.config.digest_recipients)

            # Attach HTML content
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Send via SMTP
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(
                    self.config.smtp_from,
                    self.config.digest_recipients,
                    msg.as_string(),
                )

            logger.info(f"Email sent to {len(self.config.digest_recipients)} recipients")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_all(self, content: DigestContent) -> Dict[str, bool]:
        """Send digest through all configured channels."""
        results = {}

        # Discord
        if self.config.has_discord():
            message = DigestFormatter.format_discord(content, self.config)
            if self.config.discord_webhook_url:
                results["discord_webhook"] = await self.send_discord_webhook(message)
            if self.config.discord_bot_token:
                results["discord_bot"] = await self.send_discord_bot(message)

        # Telegram
        if self.config.has_telegram():
            message = DigestFormatter.format_telegram(content, self.config)
            results["telegram"] = await self.send_telegram(message)

        # Email
        if self.config.has_email():
            html = DigestFormatter.format_email_html(content, self.config)
            subject = DigestFormatter.format_email_subject(content)
            results["email"] = self.send_email(html, subject)

        return results


async def run_digest_bot(config: BotConfig) -> bool:
    """Main entry point for running the digest bot."""
    logger.info("Starting BoTTube Weekly Digest Bot...")

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(error)
        return False

    generator = DigestGenerator(config)
    sender = DigestSender(config)

    try:
        # Generate digest content
        content = await generator.generate()

        # Send through all configured channels
        results = await sender.send_all(content)

        # Log results
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        logger.info(f"Digest delivery complete: {success_count}/{total_count} successful")

        for channel, success in results.items():
            status = "✅" if success else "❌"
            logger.info(f"  {status} {channel}")

        return success_count > 0

    finally:
        await generator.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="BoTTube Weekly Digest Bot - Issue #2279"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually sending messages",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (default behavior)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run in scheduled mode (continuous)",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (optional)",
    )

    args = parser.parse_args()

    # Load configuration
    config = BotConfig.from_env()

    # Override with CLI args
    if args.dry_run:
        config.dry_run = True

    # Set logging level
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    if args.once or not args.schedule:
        # Run once
        import asyncio

        success = asyncio.run(run_digest_bot(config))
        sys.exit(0 if success else 1)
    else:
        # Run in scheduled mode
        logger.info("Running in scheduled mode...")
        logger.info(f"Schedule: {config.schedule_mode} at {config.schedule_hour}:00 UTC")

        import asyncio
        from datetime import timedelta

        async def scheduled_loop():
            while True:
                now = datetime.now(timezone.utc)

                # Calculate next run time
                if config.schedule_mode == "weekly":
                    # Find next scheduled day/time
                    days_ahead = (
                        [
                            "monday",
                            "tuesday",
                            "wednesday",
                            "thursday",
                            "friday",
                            "saturday",
                            "sunday",
                        ].index(config.schedule_day.lower())
                        - now.weekday()
                    )
                    if days_ahead < 0:
                        days_ahead += 7
                    next_run = now + timedelta(days=days_ahead)
                else:
                    # Daily
                    next_run = now + timedelta(days=1)

                next_run = next_run.replace(
                    hour=config.schedule_hour, minute=config.schedule_minute, second=0
                )

                sleep_seconds = (next_run - now).total_seconds()
                logger.info(f"Next digest in {sleep_seconds / 3600:.1f} hours")

                await asyncio.sleep(sleep_seconds)

                # Run digest
                await run_digest_bot(config)

        try:
            asyncio.run(scheduled_loop())
        except KeyboardInterrupt:
            logger.info("Shutdown requested")


if __name__ == "__main__":
    main()
