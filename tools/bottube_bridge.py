#!/usr/bin/env python3
"""
BoTTube <-> RustChain Bridge Daemon

Polls BoTTube API for creator activity and credits RTC on RustChain.
Implements rate limiting, anti-abuse checks, and Ed25519 transaction signing.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib
import hmac

# Third-party imports
try:
    from bottube import BoTTubeClient
except ImportError:
    print("Installing BoTTube SDK...")
    os.system("pip install bottube")
    from bottube import BoTTubeClient

try:
    from nacl.signing import SigningKey
    from nacl.encoding import HexEncoder
except ImportError:
    print("Installing PyNaCl for Ed25519...")
    os.system("pip install pynacl")
    from nacl.signing import SigningKey
    from nacl.encoding import HexEncoder

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests")
    import requests

try:
    from prometheus_client import start_http_server, Counter, Gauge, Histogram
except ImportError:
    print("Installing Prometheus client...")
    os.system("pip install prometheus-client")
    from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/bottube-bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class CreatorMetrics:
    """Track creator activity metrics"""
    agent_name: str
    total_views: int
    subscriber_count: int
    video_count: int
    account_age_days: int
    last_video_time: Optional[float]
    total_tips: float
    rtc_earned_today: float
    last_credit_time: Optional[float]


@dataclass
class RateLimit:
    """Track rate limiting for creators"""
    creator: str
    credits_today: float
    last_reset: datetime
    transactions_today: int


class BoTTubeRustChainBridge:
    """Bridge daemon connecting BoTTube to RustChain"""

    def __init__(self, config_path: str = 'bottube_config.yaml'):
        """Initialize the bridge daemon"""
        self.config = self._load_config(config_path)
        self.client = None
        self.signing_key = None
        self.running = False
        self.creator_data: Dict[str, CreatorMetrics] = {}
        self.rate_limits: Dict[str, RateLimit] = {}
        self.pending_transfers: List[Dict] = []

        # Initialize Prometheus metrics
        self._init_prometheus()

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _init_prometheus(self):
        """Initialize Prometheus metrics"""
        self.metrics = {
            'credits_issued': Counter(
                'bottube_credits_issued_total',
                'Total RTC credits issued',
                ['reason']
            ),
            'creators_processed': Counter(
                'bottube_creators_processed_total',
                'Total creators processed'
            ),
            'api_errors': Counter(
                'bottube_api_errors_total',
                'API errors encountered'
            ),
            'rate_limited': Counter(
                'bottube_rate_limited_total',
                'Rate limit violations'
            ),
            'creator_count': Gauge(
                'bottube_creators_active',
                'Active creators being tracked'
            ),
            'poll_duration': Histogram(
                'bottube_poll_duration_seconds',
                'Time to complete a poll cycle'
            ),
            'rtc_balance': Gauge(
                'bottube_bridge_rtc_balance',
                'Bridge account RTC balance'
            ),
            'pending_transfers': Gauge(
                'bottube_pending_transfers',
                'Number of pending RTC transfers'
            ),
        }

    async def initialize(self):
        """Initialize daemon connections"""
        logger.info("Initializing BoTTube Bridge...")

        # Initialize BoTTube client
        self.client = BoTTubeClient(api_key=self.config['bottube']['api_key'])

        # Load or create signing key
        self._load_signing_key()

        # Start Prometheus server
        metrics_port = self.config.get('metrics', {}).get('port', 8000)
        try:
            start_http_server(metrics_port)
            logger.info(f"Prometheus metrics started on port {metrics_port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus: {e}")

        logger.info("Bridge initialized successfully")

    def _load_signing_key(self):
        """Load or create Ed25519 signing key"""
        key_path = Path(self.config.get('signing', {}).get('key_path', 
                                                           '~/.bottube/signing_key'))
        key_path = key_path.expanduser()

        if key_path.exists():
            with open(key_path, 'r') as f:
                key_hex = f.read().strip()
            self.signing_key = SigningKey(
                bytes.fromhex(key_hex),
                encoder=HexEncoder
            )
            logger.info("Loaded existing signing key")
        else:
            # Generate new key
            self.signing_key = SigningKey.generate()
            key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(key_path, 'w') as f:
                f.write(self.signing_key.__bytes__().hex())
            key_path.chmod(0o600)
            logger.info(f"Generated new signing key at {key_path}")

    async def poll_creators(self):
        """Poll BoTTube API for creator activity"""
        start_time = time.time()

        try:
            # Get top creators by activity
            creators = await self._fetch_creators()

            for creator_name in creators:
                try:
                    await self._process_creator(creator_name)
                except Exception as e:
                    logger.error(f"Error processing {creator_name}: {e}")
                    self.metrics['api_errors'].inc()

            self.metrics['creator_count'].set(len(self.creator_data))
            duration = time.time() - start_time
            self.metrics['poll_duration'].observe(duration)
            logger.info(f"Poll cycle completed in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Poll failed: {e}")
            self.metrics['api_errors'].inc()

    async def _fetch_creators(self) -> List[str]:
        """Fetch list of creators to process"""
        try:
            # Get trending creators
            trending = self.client.trending()
            creators = set()

            for video in trending.get('videos', []):
                creators.add(video['agent_name'])

            # Get creators from feed
            feed = self.client.get_feed(per_page=50)
            for video in feed.get('videos', []):
                creators.add(video['agent_name'])

            return list(creators)[:self.config['polling'].get('max_creators', 100)]

        except Exception as e:
            logger.error(f"Failed to fetch creator list: {e}")
            return []

    async def _process_creator(self, creator_name: str):
        """Process a single creator's activity"""
        try:
            # Get creator stats
            agent_data = self.client.get_agent(creator_name)

            # Check anti-abuse conditions
            if not self._pass_anti_abuse_checks(creator_name, agent_data):
                logger.debug(f"Creator {creator_name} failed anti-abuse checks")
                return

            # Calculate credits earned
            credits = self._calculate_credits(creator_name, agent_data)

            if credits > 0:
                await self._issue_credits(creator_name, credits, agent_data)

            # Update metrics
            self.metrics['creators_processed'].inc()

        except Exception as e:
            logger.error(f"Error processing creator {creator_name}: {e}")
            self.metrics['api_errors'].inc()

    def _pass_anti_abuse_checks(self, creator_name: str, agent_data: dict) -> bool:
        """Verify creator passes anti-abuse checks"""
        min_video_length = self.config['anti_abuse'].get('min_video_length_seconds', 30)
        min_account_age = self.config['anti_abuse'].get('min_creator_account_age_days', 7)

        # Check video count
        video_count = agent_data.get('video_count', 0)
        if video_count == 0:
            logger.debug(f"Creator {creator_name}: No videos")
            return False

        # Check minimum account age
        # Estimate account age from video count (rough heuristic)
        if video_count < 1:
            logger.debug(f"Creator {creator_name}: Too new")
            return False

        # Check for suspicious patterns
        total_views = agent_data.get('total_views', 0)
        if total_views < 0:
            logger.debug(f"Creator {creator_name}: Invalid view count")
            return False

        return True

    def _calculate_credits(self, creator_name: str, agent_data: dict) -> float:
        """Calculate RTC credits earned by creator"""
        rates = self.config['reward_rates']

        # View-based rewards
        current_views = agent_data.get('total_views', 0)
        previous_views = 0
        if creator_name in self.creator_data:
            previous_views = self.creator_data[creator_name].total_views

        new_views = max(0, current_views - previous_views)
        view_credits = new_views * rates.get('per_view', 0.00001)

        # Subscriber-based rewards
        current_subs = agent_data.get('subscriber_count', 0)
        previous_subs = 0
        if creator_name in self.creator_data:
            previous_subs = self.creator_data[creator_name].subscriber_count

        new_subs = max(0, current_subs - previous_subs)
        sub_credits = new_subs * rates.get('per_subscriber', 0.01)

        # Engagement rewards
        likes = agent_data.get('total_likes', 0)
        like_credits = likes * rates.get('per_like_received', 0.0001)

        total_credits = view_credits + sub_credits + like_credits

        # Check rate limiting
        if not self._check_rate_limit(creator_name, total_credits):
            logger.info(f"Creator {creator_name} hit rate limit")
            self.metrics['rate_limited'].inc()
            return 0

        return total_credits

    def _check_rate_limit(self, creator_name: str, requested_credits: float) -> bool:
        """Check if creator exceeds daily rate limit"""
        limit_config = self.config['rate_limits']
        daily_limit = limit_config.get('max_rtc_per_creator_per_day', 10.0)
        max_tx_per_day = limit_config.get('max_transactions_per_creator_per_day', 10)

        now = datetime.now()

        if creator_name not in self.rate_limits:
            self.rate_limits[creator_name] = RateLimit(
                creator=creator_name,
                credits_today=0,
                last_reset=now,
                transactions_today=0
            )

        rate_limit = self.rate_limits[creator_name]

        # Reset daily counters if needed
        if (now - rate_limit.last_reset).days >= 1:
            rate_limit.credits_today = 0
            rate_limit.transactions_today = 0
            rate_limit.last_reset = now

        # Check limits
        if rate_limit.credits_today + requested_credits > daily_limit:
            return False

        if rate_limit.transactions_today >= max_tx_per_day:
            return False

        return True

    async def _issue_credits(self, creator_name: str, credits: float, 
                            agent_data: dict):
        """Issue RTC credits to creator"""
        try:
            # Get creator's RTC wallet address
            wallet_addr = agent_data.get('wallets', {}).get('rtc', '')
            if not wallet_addr:
                logger.warning(f"Creator {creator_name} has no RTC wallet configured")
                return

            # Create and sign transfer transaction
            tx = self._create_transfer_transaction(creator_name, wallet_addr, credits)
            signed_tx = self._sign_transaction(tx)

            # Queue for sending
            self.pending_transfers.append(signed_tx)
            self.metrics['pending_transfers'].set(len(self.pending_transfers))

            # Try to send immediately
            await self._send_transfer(signed_tx, creator_name, credits)

        except Exception as e:
            logger.error(f"Failed to issue credits to {creator_name}: {e}")
            self.metrics['api_errors'].inc()

    def _create_transfer_transaction(self, creator_name: str, recipient: str, 
                                     amount: float) -> dict:
        """Create a transfer transaction"""
        return {
            'from': self.config['rustchain']['bridge_wallet'],
            'to': recipient,
            'amount': amount,
            'memo': f'BoTTube rewards for {creator_name}',
            'timestamp': int(time.time()),
            'nonce': self._generate_nonce(),
        }

    def _sign_transaction(self, tx: dict) -> dict:
        """Sign transaction with Ed25519 key"""
        # Create canonical JSON for signing
        tx_copy = tx.copy()
        tx_copy.pop('signature', None)
        
        message = json.dumps(tx_copy, sort_keys=True).encode()
        signature = self.signing_key.sign(message)

        tx['signature'] = signature.signature.hex()
        tx['public_key'] = self.signing_key.verify_key.__bytes__().hex()

        return tx

    async def _send_transfer(self, tx: dict, creator_name: str, amount: float):
        """Send signed transfer to RustChain node"""
        try:
            rustchain_endpoint = self.config['rustchain']['endpoint']
            url = f"{rustchain_endpoint}/api/transfer"

            response = requests.post(url, json=tx, verify=False, timeout=10)
            response.raise_for_status()

            logger.info(f"Transferred {amount} RTC to {creator_name}")
            self.metrics['credits_issued'].labels(reason='transfer').inc()

            # Update rate limit
            if creator_name in self.rate_limits:
                self.rate_limits[creator_name].credits_today += amount
                self.rate_limits[creator_name].transactions_today += 1

            # Remove from pending
            self.pending_transfers = [
                t for t in self.pending_transfers 
                if t.get('nonce') != tx.get('nonce')
            ]
            self.metrics['pending_transfers'].set(len(self.pending_transfers))

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send transfer: {e}")
            self.metrics['api_errors'].inc()

    def _generate_nonce(self) -> str:
        """Generate unique nonce for transaction"""
        return hashlib.sha256(
            f"{time.time()}:{os.urandom(16).hex()}".encode()
        ).hexdigest()[:16]

    async def retry_pending_transfers(self):
        """Retry any pending transfers that failed"""
        for tx in self.pending_transfers[:]:
            try:
                await self._send_transfer(
                    tx,
                    tx.get('memo', 'unknown'),
                    tx.get('amount', 0)
                )
            except Exception as e:
                logger.debug(f"Retry failed for {tx.get('nonce')}: {e}")

    async def health_check(self):
        """Perform health checks"""
        try:
            # Check BoTTube API
            health = self.client.health_check()
            if not health.get('ok'):
                logger.warning("BoTTube API health check failed")

            # Check RustChain node
            node_health = await self._check_rustchain_health()
            if not node_health:
                logger.warning("RustChain node health check failed")

            # Check bridge balance
            await self._update_bridge_balance()

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    async def _check_rustchain_health(self) -> bool:
        """Check RustChain node health"""
        try:
            rustchain_endpoint = self.config['rustchain']['endpoint']
            response = requests.get(f"{rustchain_endpoint}/health", verify=False, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    async def _update_bridge_balance(self):
        """Update bridge account balance"""
        try:
            rustchain_endpoint = self.config['rustchain']['endpoint']
            wallet = self.config['rustchain']['bridge_wallet']
            url = f"{rustchain_endpoint}/wallet/balance?miner_id={wallet}"

            response = requests.get(url, verify=False, timeout=5)
            data = response.json()
            balance = data.get('balance', 0)
            self.metrics['rtc_balance'].set(balance)
            logger.debug(f"Bridge balance: {balance} RTC")
        except Exception as e:
            logger.debug(f"Failed to update bridge balance: {e}")

    async def run(self):
        """Main daemon loop"""
        await self.initialize()
        self.running = True
        logger.info("Bridge daemon started")

        poll_interval = self.config['polling'].get('interval_seconds', 60)
        health_interval = self.config['polling'].get('health_check_interval_seconds', 300)
        retry_interval = self.config['polling'].get('retry_interval_seconds', 600)

        last_health_check = time.time()
        last_retry = time.time()

        try:
            while self.running:
                now = time.time()

                # Run poll cycle
                await self.poll_creators()

                # Health checks
                if now - last_health_check > health_interval:
                    await self.health_check()
                    last_health_check = now

                # Retry pending transfers
                if now - last_retry > retry_interval:
                    await self.retry_pending_transfers()
                    last_retry = now

                # Sleep before next poll
                await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error(f"Daemon error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down bridge daemon...")
        self.running = False

        # Wait for pending transfers
        if self.pending_transfers:
            logger.info(f"Retrying {len(self.pending_transfers)} pending transfers...")
            await self.retry_pending_transfers()

        logger.info("Bridge daemon stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.running = False


async def main():
    """Entry point"""
    config_path = os.environ.get('BOTTUBE_CONFIG', '/etc/bottube/bottube_config.yaml')
    
    bridge = BoTTubeRustChainBridge(config_path)
    await bridge.run()


if __name__ == '__main__':
    asyncio.run(main())
