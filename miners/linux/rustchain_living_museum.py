#!/usr/bin/env python3
"""
RustChain Living Museum - Discord + Twitter/X Announcer
========================================================
Posts engaging updates about vintage machines keeping the chain alive.
Features rotating content: leaderboards, machine spotlights, fun facts, fleet stats.
Posts to both Discord and Twitter/X simultaneously.
"""

import discord
from discord.ext import tasks
import tweepy
import requests
import os
import sys
import random
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load both env files
load_dotenv('/home/sophia/.env.discord')
load_dotenv('/home/sophia/.env.twitter')
sys.stdout.reconfigure(line_buffering=True)

# Configuration
RUSTCHAIN_API = "http://50.28.86.131:8099"
CHANNEL_NAME = "rustchain-relay"
ANNOUNCE_INTERVAL_HOURS = 6  # Post every 6 hours
TWITTER_ENABLED = True  # Set to False to disable Twitter posting

# Emojis for different content
ARCH_EMOJIS = {
    "G4": "\U0001F34E", "G5": "\U0001F5A5", "G3": "\U0001F4DF", "g4": "\U0001F34E",
    "retro": "\U0001F579", "486": "\U0001F4BE", "pentium": "\U0001F532",
    "apple_silicon": "\U0001F34F", "modern": "\U0001F4BB", "x86_64": "\U0001F5A5",
    "Power Macintosh": "\U0001F34E"
}

BADGE_EMOJIS = {
    "Oxidized Legend": "\U0001F3C6", "Tetanus Master": "\U0001F9A0",
    "Patina Veteran": "\U0001F396", "Rust Warrior": "\U00002694",
    "Corroded Knight": "\U0001F6E1", "Tarnished Squire": "\U0001F4DC", "Fresh Metal": "\U00002728"
}

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [MUSEUM] {msg}", flush=True)

def fetch_api(endpoint):
    """Fetch data from RustChain API."""
    try:
        resp = requests.get(f"{RUSTCHAIN_API}{endpoint}", timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        log(f"API error {endpoint}: {e}")
        return None

# ============== Twitter/X Integration ==============

def get_twitter_client():
    """Initialize Twitter API v2 client."""
    try:
        api_key = os.getenv('TWITTER_API_KEY')
        api_secret = os.getenv('TWITTER_API_SECRET')
        access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        access_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        if not all([api_key, api_secret, access_token, access_secret]):
            log("Twitter credentials incomplete - disabling Twitter")
            return None

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret
        )
        log("Twitter client initialized")
        return client
    except Exception as e:
        log(f"Twitter init error: {e}")
        return None

def post_to_twitter(client, text):
    """Post a tweet. Returns True on success."""
    if not client or not TWITTER_ENABLED:
        return False
    try:
        # Twitter limit is 280 chars
        if len(text) > 280:
            text = text[:277] + "..."
        response = client.create_tweet(text=text)
        log(f"Tweet posted: {response.data['id']}")
        return True
    except Exception as e:
        log(f"Twitter post error: {e}")
        return False

def format_leaderboard_tweet(data, stats, fact):
    """Format leaderboard data for Twitter."""
    if not data:
        return None

    top3 = data.get('leaderboard', [])[:3]
    total = stats.get('total_machines', 0) if stats else '?'

    tweet = "\U0001F980 HALL OF RUST - Top 3\n\n"
    for m in top3:
        arch = m.get('device_arch', '?')
        emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
        tweet += f"{emoji} #{m['rank']} {arch} ({m.get('manufacture_year', '?')}) - Score: {m['rust_score']:.0f}\n"

    tweet += f"\n\U0001F3DB {total} machines in the Living Museum"

    if fact:
        remaining = 280 - len(tweet) - 5
        fact_text = fact.get('fact', '')[:remaining]
        if len(fact_text) > 20:
            tweet += f"\n\n\U0001F4A1 {fact_text}"

    return tweet

def format_spotlight_tweet(machine):
    """Format machine spotlight for Twitter."""
    if not machine:
        return None

    arch = machine.get('device_arch', 'unknown')
    emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
    year = machine.get('manufacture_year', '?')
    age = machine.get('age_years', '?')
    score = machine.get('rust_score', 0)
    badge = machine.get('badge', '')

    tweet = f"{emoji} Machine Spotlight {emoji}\n\n"
    tweet += f"Architecture: {arch}\n"
    tweet += f"Year: {year} ({age} years old)\n"
    tweet += f"Rust Score: {score:.0f}\n"
    if badge:
        tweet += f"Badge: {badge}\n"

    tweet += "\nVintage silicon keeping the chain alive! \U0001F980"

    if machine.get('fun_fact'):
        remaining = 280 - len(tweet) - 5
        if remaining > 30:
            fact = machine['fun_fact'][:remaining-3] + "..."
            tweet += f"\n\n{fact}"

    return tweet

def format_fleet_tweet(breakdown, stats):
    """Format fleet stats for Twitter."""
    if not breakdown:
        return None

    tweet = "\U0001F3DB RustChain Living Museum - Fleet Report\n\n"

    for arch_data in breakdown.get('breakdown', [])[:4]:
        arch = arch_data['architecture']
        emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
        count = arch_data['count']
        oldest = arch_data['oldest_year']
        tweet += f"{emoji} {arch}: {count} (oldest: {oldest})\n"

    if stats:
        total = stats.get('total_machines', 0)
        tweet += f"\n\U0001F5A5 Total: {total} machines"

    tweet += "\n\n#VintageComputing #RustChain"

    return tweet

def format_timeline_tweet(timeline):
    """Format timeline for Twitter."""
    if not timeline:
        return None

    entries = timeline.get('timeline', [])[:3]
    if not entries:
        return None

    tweet = "\U0001F4C5 Hall of Rust - Recent Inductions\n\n"

    for entry in entries:
        date = entry['date']
        count = entry['machines_joined']
        archs = entry['architectures']

        # Count unique archs
        arch_set = set(archs)
        arch_str = ", ".join(list(arch_set)[:3])
        tweet += f"{date}: +{count} ({arch_str})\n"

    tweet += "\nThe museum grows! \U0001F980\n#RustChain #VintageHardware"

    return tweet

# ============== Discord Bot ==============

class LivingMuseumBot(discord.Client):
    def __init__(self, twitter_client=None):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        super().__init__(intents=intents)
        self.channel = None
        self.post_count = 0
        self.twitter = twitter_client

    async def on_ready(self):
        log(f"Logged in as {self.user}")

        for guild in self.guilds:
            for channel in guild.text_channels:
                if CHANNEL_NAME in channel.name.lower():
                    self.channel = channel
                    log(f"Found #{channel.name} in {guild.name}")
                    break
            if self.channel:
                break

        if not self.channel:
            log(f"ERROR: Could not find #{CHANNEL_NAME}!")
            return

        # Start the rotation loop
        self.museum_loop.start()
        log(f"Museum loop started - posting every {ANNOUNCE_INTERVAL_HOURS} hours")
        if self.twitter:
            log("Twitter posting ENABLED")
        else:
            log("Twitter posting DISABLED")

    @tasks.loop(hours=ANNOUNCE_INTERVAL_HOURS)
    async def museum_loop(self):
        if not self.channel:
            return

        # Rotate between different post types
        post_types = [
            self.post_leaderboard,
            self.post_machine_spotlight,
            self.post_fleet_stats,
            self.post_timeline_update
        ]

        # Pick based on rotation
        post_func = post_types[self.post_count % len(post_types)]
        self.post_count += 1

        log(f"Posting: {post_func.__name__}")
        await post_func()

    async def post_leaderboard(self):
        """Post the top 10 rustiest machines."""
        data = fetch_api("/hall/leaderboard?limit=10")
        stats = fetch_api("/hall/stats")
        fact = fetch_api("/hall/random_fact")

        if not data:
            return

        # === Discord Embed ===
        embed = discord.Embed(
            title="\U0001F980 HALL OF RUST - Leaderboard \U0001F980",
            description="*The rustiest machines keeping the chain alive*",
            color=0xB7410E,
            timestamp=datetime.now(timezone.utc)
        )

        leaderboard_text = ""
        for m in data.get('leaderboard', [])[:10]:
            rank = m['rank']
            arch = m.get('device_arch') or 'unknown'
            arch_emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
            miner_id = m['miner_id']
            miner_short = miner_id[:20] + '..' if len(miner_id) > 22 else miner_id
            score = m['rust_score']
            year = m.get('manufacture_year', '?')

            if rank == 1:
                leaderboard_text += f"\U0001F451 **#{rank}** `{miner_short}`\n"
                leaderboard_text += f"    {arch_emoji} {arch} | Score: **{score:.0f}** | Year: {year}\n\n"
            else:
                leaderboard_text += f"**#{rank}** `{miner_short}`\n"
                leaderboard_text += f"    {arch_emoji} {arch} | Score: {score:.0f} | Year: {year}\n"

        embed.add_field(name="\U0001F3C5 Top 10 Rustiest Machines", value=leaderboard_text[:1024], inline=False)

        if stats:
            total = stats.get('total_machines', 0)
            highest = stats.get('highest_rust_score', 0)
            avg = stats.get('average_rust_score', 0)
            deceased = stats.get('deceased_machines', 0)
            plague = stats.get('capacitor_plague_survivors', 0)
            stats_text = f"""
\U0001F4CA **Total Machines Inducted:** {total}
\U0001F3AF **Highest Rust Score:** {highest:.0f}
\U0001F4C8 **Average Rust Score:** {avg:.1f}
\U00002620 **Deceased Machines:** {deceased}
\U000026A1 **Capacitor Plague Survivors:** {plague}
"""
            embed.add_field(name="\U0001F4CB Hall Statistics", value=stats_text, inline=False)

        if fact:
            embed.add_field(name="\U0001F4A1 Did You Know?", value=f"*{fact.get('fact', '')}*", inline=False)

        oldest = stats.get('oldest_machine', {}) if stats else {}
        oldest_id = oldest.get('miner_id', 'unknown')[:25]
        oldest_year = oldest.get('year', '?')
        embed.set_footer(text=f"\U0001F474 Oldest: {oldest_id} ({oldest_year})")

        await self.channel.send(embed=embed)
        log("Posted leaderboard to Discord")

        # === Twitter ===
        tweet = format_leaderboard_tweet(data, stats, fact)
        if tweet:
            post_to_twitter(self.twitter, tweet)

    async def post_machine_spotlight(self):
        """Spotlight a random vintage machine."""
        machine = fetch_api("/hall/machine_of_the_day")

        if not machine:
            return

        arch = machine.get('device_arch', 'unknown')
        arch_emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
        badge_emoji = BADGE_EMOJIS.get(machine.get('badge', ''), "\U0001F527")

        miner_id = machine.get('miner_id', 'Unknown')
        miner_short = miner_id[:30] + '...' if len(miner_id) > 30 else miner_id

        # === Discord Embed ===
        embed = discord.Embed(
            title=f"{arch_emoji} Machine Spotlight {arch_emoji}",
            description="*Celebrating the vintage hardware keeping RustChain alive*",
            color=0xFFD700,
            timestamp=datetime.now(timezone.utc)
        )

        year = machine.get('manufacture_year', 'Unknown')
        age = machine.get('age_years', '?')
        score = machine.get('rust_score', 0)
        badge = machine.get('badge', 'Unknown')
        attestations = machine.get('total_attestations', 0)

        details = f"""
\U0001F3F7 **ID:** `{miner_short}`
{arch_emoji} **Architecture:** {arch}
\U0001F4C5 **Manufacture Year:** {year}
\U0001F474 **Age:** {age} years old
\U0001F980 **Rust Score:** {score:.0f}
{badge_emoji} **Badge:** {badge}
\U0001F4CA **Total Attestations:** {attestations}
"""
        embed.add_field(name="Machine Profile", value=details, inline=False)

        first_seen = machine.get('first_attestation')
        if first_seen:
            date_str = datetime.fromtimestamp(first_seen).strftime('%Y-%m-%d %H:%M UTC')
            embed.add_field(name="\U0001F550 First Attestation", value=date_str, inline=True)

        if machine.get('fun_fact'):
            embed.add_field(name="\U0001F4A1 Fun Fact", value=f"*{machine['fun_fact']}*", inline=False)

        embed.set_footer(text="Every machine has a story. This one is still being written.")

        await self.channel.send(embed=embed)
        log(f"Posted spotlight for {miner_short} to Discord")

        # === Twitter ===
        tweet = format_spotlight_tweet(machine)
        if tweet:
            post_to_twitter(self.twitter, tweet)

    async def post_fleet_stats(self):
        """Post fleet breakdown by architecture."""
        breakdown = fetch_api("/hall/fleet_breakdown")
        stats = fetch_api("/hall/stats")

        if not breakdown:
            return

        # === Discord Embed ===
        embed = discord.Embed(
            title="\U0001F3DB Living Museum - Fleet Report \U0001F3DB",
            description="*Architecture breakdown of machines in the Hall of Rust*",
            color=0x4169E1,
            timestamp=datetime.now(timezone.utc)
        )

        fleet_text = ""
        for arch_data in breakdown.get('breakdown', [])[:8]:
            arch = arch_data['architecture']
            emoji = ARCH_EMOJIS.get(arch, "\U0001F527")
            count = arch_data['count']
            oldest = arch_data['oldest_year']
            avg_score = arch_data['avg_rust_score']

            fleet_text += f"{emoji} **{arch}:** {count} machines\n"
            fleet_text += f"    \U0001F4C5 Oldest: {oldest} | \U0001F980 Avg Score: {avg_score:.0f}\n"

        embed.add_field(name="\U0001F4CA Fleet Composition", value=fleet_text[:1024], inline=False)

        if stats:
            total = stats.get('total_machines', 0)
            highest = stats.get('highest_rust_score', 0)
            avg = stats.get('average_rust_score', 0)
            summary = f"""
\U0001F5A5 **Total Fleet Size:** {total} machines
\U0001F3C6 **Peak Rust Score:** {highest:.0f}
\U0001F4C8 **Fleet Average:** {avg:.1f}
"""
            embed.add_field(name="\U0001F4CB Summary", value=summary, inline=False)

        messages = [
            "Every electron through these circuits is a tribute to engineering that lasts.",
            "24-year-old silicon still hashing. They don't make 'em like they used to.",
            "These machines have seen Y2K, the dot-com crash, and the rise of smartphones.",
            "Vintage hardware: slower clock speeds, faster heartbeats.",
            "The patina of age only makes them more valuable to the chain."
        ]
        embed.set_footer(text=random.choice(messages))

        await self.channel.send(embed=embed)
        log("Posted fleet stats to Discord")

        # === Twitter ===
        tweet = format_fleet_tweet(breakdown, stats)
        if tweet:
            post_to_twitter(self.twitter, tweet)

    async def post_timeline_update(self):
        """Post recent induction activity."""
        timeline = fetch_api("/hall/timeline")
        fact = fetch_api("/hall/random_fact")

        if not timeline:
            return

        # === Discord Embed ===
        embed = discord.Embed(
            title="\U0001F4C5 Hall of Rust - Recent Inductions \U0001F4C5",
            description="*New machines joining the living museum*",
            color=0x32CD32,
            timestamp=datetime.now(timezone.utc)
        )

        timeline_text = ""
        for entry in timeline.get('timeline', [])[:7]:
            date = entry['date']
            count = entry['machines_joined']
            archs = entry['architectures']

            arch_counts = {}
            for a in archs:
                arch_counts[a] = arch_counts.get(a, 0) + 1

            arch_summary = ", ".join([f"{ARCH_EMOJIS.get(a, '\U0001F527')}{c}" for a, c in arch_counts.items()])

            timeline_text += f"**{date}:** +{count} machines\n"
            timeline_text += f"    {arch_summary}\n"

        embed.add_field(name="\U0001F550 Recent Activity", value=timeline_text[:1024], inline=False)

        if fact:
            embed.add_field(name="\U0001F4A1 Vintage Wisdom", value=f"*{fact.get('fact', '')}*", inline=False)

        embed.set_footer(text="The museum grows. The chain strengthens.")

        await self.channel.send(embed=embed)
        log("Posted timeline to Discord")

        # === Twitter ===
        tweet = format_timeline_tweet(timeline)
        if tweet:
            post_to_twitter(self.twitter, tweet)

def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        log("ERROR: No DISCORD_TOKEN found!")
        return

    log("Starting RustChain Living Museum Bot...")
    log(f"API: {RUSTCHAIN_API}")
    log(f"Channel: {CHANNEL_NAME}")
    log(f"Interval: {ANNOUNCE_INTERVAL_HOURS} hours")

    # Initialize Twitter client
    twitter_client = get_twitter_client() if TWITTER_ENABLED else None

    client = LivingMuseumBot(twitter_client=twitter_client)
    client.run(token)

if __name__ == "__main__":
    main()
