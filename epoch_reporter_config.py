// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os

# Platform API Configuration
DISCORD_CONFIG = {
    'webhook_url': os.environ.get('DISCORD_WEBHOOK_URL', ''),
    'enabled': os.environ.get('DISCORD_ENABLED', 'false').lower() == 'true',
    'timeout': 30
}

MOLTBOOK_CONFIG = {
    'api_endpoint': os.environ.get('MOLTBOOK_API_URL', 'https://api.moltbook.com/posts'),
    'api_key': os.environ.get('MOLTBOOK_API_KEY', ''),
    'enabled': os.environ.get('MOLTBOOK_ENABLED', 'false').lower() == 'true',
    'timeout': 30
}

TWITTER_CONFIG = {
    'api_key': os.environ.get('TWITTER_API_KEY', ''),
    'api_secret': os.environ.get('TWITTER_API_SECRET', ''),
    'access_token': os.environ.get('TWITTER_ACCESS_TOKEN', ''),
    'access_token_secret': os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', ''),
    'enabled': os.environ.get('TWITTER_ENABLED', 'false').lower() == 'true'
}

# Rustchain API Configuration
RUSTCHAIN_API = {
    'base_url': os.environ.get('RUSTCHAIN_API_URL', 'https://50.28.86.131'),
    'epoch_endpoint': '/epoch',
    'miners_endpoint': '/miners',
    'explorer_url': 'https://50.28.86.131/explorer',
    'timeout': 15
}

# Epoch Summary Templates
DISCORD_TEMPLATE = """
📊 **Epoch {epoch_num} Complete**

💰 {total_rewards} RTC distributed to {miner_count} miners
🏆 Top earner: **{top_miner}** ({top_reward} RTC{top_multiplier})
⛏️ Active miners: {miner_count} ({miner_breakdown})
📦 Block height: {block_height:,}
💎 Total RTC mined: {total_mined}

🔍 Explorer: {explorer_url}
"""

MOLTBOOK_TEMPLATE = """
📊 Epoch {epoch_num} Complete

💰 {total_rewards} RTC distributed to {miner_count} miners
🏆 Top earner: {top_miner} ({top_reward} RTC{top_multiplier})
⛏️ Active miners: {miner_count} ({miner_breakdown})
📦 Block height: {block_height:,}
💎 Total RTC mined: {total_mined}

Explorer: {explorer_url}
"""

TWITTER_TEMPLATE = """
📊 Epoch {epoch_num} Complete

💰 {total_rewards} RTC → {miner_count} miners
🏆 {top_miner} ({top_reward} RTC{top_multiplier})
⛏️ {miner_count} active ({miner_breakdown})
📦 Block: {block_height:,}

{explorer_url}
"""

# Miner Type Mappings
MINER_TYPE_EMOJIS = {
    'G4': '🟢',
    'G5': '🔵',
    'POWER8': '🟣',
    'modern': '⚡',
    'legacy': '🔶'
}

# Formatting Configuration
FORMAT_CONFIG = {
    'decimal_places': 3,
    'max_tweet_length': 280,
    'miner_breakdown_max': 5,
    'top_miners_count': 1
}

# Posting Schedule
SCHEDULE_CONFIG = {
    'check_interval': 60,  # seconds
    'post_delay': 30,      # seconds after epoch detection
    'retry_attempts': 3,
    'retry_delay': 10      # seconds between retries
}

# Database Configuration
DB_CONFIG = {
    'db_path': 'epoch_reporter.db',
    'table_name': 'posted_epochs'
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': os.environ.get('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'epoch_reporter.log'
}
