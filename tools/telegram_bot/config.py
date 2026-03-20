# SPDX-License-Identifier: MIT

import os


# Bot Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
BOT_WEBHOOK_URL = os.getenv('BOT_WEBHOOK_URL', '')
BOT_PORT = int(os.getenv('BOT_PORT', '8443'))

# RustChain API Configuration
API_BASE_URL = 'http://50.28.86.131'
API_ENDPOINTS = {
    'miners': f'{API_BASE_URL}/api/miners',
    'epoch': f'{API_BASE_URL}/epoch',
    'health': f'{API_BASE_URL}/api/health',
    'node_info': f'{API_BASE_URL}/api/node',
    'blocks': f'{API_BASE_URL}/api/blocks'
}

# Raydium API for price data
RAYDIUM_API_URL = 'https://api.raydium.io/v2/sdk/liquidity/mainnet.json'
WRTC_TOKEN_MINT = 'WRTC_MINT_ADDRESS_HERE'  # Update with actual wRTC mint address

# Database Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_data.db')

# Alert Settings
PRICE_ALERT_THRESHOLD = 0.05  # 5% price change
MINING_ALERT_ENABLED = True
EPOCH_ALERT_ENABLED = True

# Rate Limiting
API_REQUEST_TIMEOUT = 10
CACHE_DURATION = 30  # seconds

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Admin Configuration
ADMIN_CHAT_IDS = []  # Add admin chat IDs for notifications
