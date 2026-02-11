#!/usr/bin/env python3
"""
RustChain Mining Leaderboard Bot
Fetches miner data and posts formatted leaderboards to Discord
"""

import json
import requests
import time
from datetime import datetime
from collections import defaultdict
import sys
import os

# Configuration
CONFIG_FILE = 'leaderboard-config.json'
DEFAULT_CONFIG = {
    'node_url': 'https://50.28.86.131',
    'discord_webhook': '',
    'top_n': 10,
    'frequency_hours': 24,
    'cache_file': 'leaderboard-cache.json'
}

class LeaderboardBot:
    def __init__(self, config_path=CONFIG_FILE):
        self.config = self.load_config(config_path)
        self.node_url = self.config['node_url']
        self.webhook_url = self.config['discord_webhook']
        self.cache = self.load_cache()
        
    def load_config(self, path):
        """Load configuration from file or create default"""
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        else:
            with open(path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print(f"Created default config at {path}")
            print("Please edit the config file and set your Discord webhook URL")
            sys.exit(1)
    
    def load_cache(self):
        """Load historical data cache"""
        cache_file = self.config.get('cache_file', 'leaderboard-cache.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        return {'history': [], 'last_run': None}
    
    def save_cache(self):
        """Save cache to disk"""
        cache_file = self.config.get('cache_file', 'leaderboard-cache.json')
        with open(cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def fetch_miners(self):
        """Fetch active miners from node API"""
        try:
            response = requests.get(
                f"{self.node_url}/api/miners",
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get('miners', [])
        except Exception as e:
            print(f"Error fetching miners: {e}")
            return []
    
    def fetch_balance(self, miner_id):
        """Fetch balance for a specific miner"""
        try:
            response = requests.get(
                f"{self.node_url}/wallet/balance",
                params={'miner_id': miner_id},
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return float(data.get('balance', 0))
        except Exception as e:
            print(f"Error fetching balance for {miner_id}: {e}")
        return 0.0
    
    def fetch_epoch(self):
        """Fetch current epoch information"""
        try:
            response = requests.get(
                f"{self.node_url}/epoch",
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching epoch: {e}")
        return None
    
    def generate_leaderboard(self):
        """Generate complete leaderboard data"""
        miners = self.fetch_miners()
        if not miners:
            return None
        
        # Fetch balances for all miners
        leaderboard = []
        for miner in miners:
            miner_id = miner.get('id') or miner.get('miner_id')
            if not miner_id:
                continue
            
            balance = self.fetch_balance(miner_id)
            leaderboard.append({
                'id': miner_id,
                'name': miner.get('name', 'Unknown'),
                'hardware': miner.get('hardware', 'Unknown'),
                'architecture': miner.get('architecture', 'Unknown'),
                'balance': balance,
                'uptime': miner.get('uptime_percent', 0),
                'last_seen': miner.get('last_attestation')
            })
            
            # Rate limiting
            time.sleep(0.1)
        
        # Sort by balance
        leaderboard.sort(key=lambda x: x['balance'], reverse=True)
        
        return {
            'miners': leaderboard,
            'epoch': self.fetch_epoch(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def calculate_architecture_distribution(self, miners):
        """Calculate percentage breakdown by architecture"""
        arch_count = defaultdict(int)
        total = len(miners)
        
        for miner in miners:
            arch = miner['architecture']
            # Simplify architecture names
            if 'PowerPC' in arch or 'G4' in arch or 'G5' in arch:
                arch = 'PowerPC'
            elif 'ARM' in arch:
                arch = 'ARM'
            elif 'x86' in arch or 'Intel' in arch or 'AMD' in arch:
                arch = 'x86_64'
            else:
                arch = 'Other'
            arch_count[arch] += 1
        
        # Calculate percentages
        distribution = {}
        for arch, count in arch_count.items():
            distribution[arch] = {
                'count': count,
                'percent': (count / total * 100) if total > 0 else 0
            }
        
        return distribution
    
    def find_rising_star(self, current_data):
        """Find miner with biggest balance increase"""
        if not self.cache.get('history'):
            return None
        
        # Get previous snapshot
        prev_snapshot = self.cache['history'][-1] if self.cache['history'] else None
        if not prev_snapshot:
            return None
        
        prev_miners = {m['id']: m['balance'] for m in prev_snapshot.get('miners', [])}
        current_miners = current_data['miners']
        
        max_gain = 0
        rising_star = None
        
        for miner in current_miners:
            miner_id = miner['id']
            prev_balance = prev_miners.get(miner_id, 0)
            gain = miner['balance'] - prev_balance
            
            if gain > max_gain:
                max_gain = gain
                rising_star = {
                    'miner': miner,
                    'gain': gain,
                    'previous': prev_balance
                }
        
        return rising_star
    
    def format_discord_message(self, data):
        """Format leaderboard data for Discord"""
        miners = data['miners']
        epoch = data.get('epoch', {})
        top_n = self.config['top_n']
        
        # Header
        message = f"# ⛏️ RustChain Mining Leaderboard\n\n"
        message += f"**📊 Network Statistics**\n"
        message += f"• Active Miners: **{len(miners)}**\n"
        
        if epoch:
            message += f"• Current Epoch: **{epoch.get('epoch', 'N/A')}**\n"
            message += f"• Block Height: **{epoch.get('block_height', 'N/A')}**\n"
        
        total_rtc = sum(m['balance'] for m in miners)
        message += f"• Total RTC Distributed: **{total_rtc:.4f}**\n"
        message += f"\n"
        
        # Top miners
        message += f"## 🏆 Top {min(top_n, len(miners))} Miners\n"
        message += "```\n"
        message += f"{'Rank':<5} {'Miner ID':<20} {'Balance':<12} {'Hardware':<15}\n"
        message += "─" * 65 + "\n"
        
        for i, miner in enumerate(miners[:top_n], 1):
            rank_icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            miner_id = miner['id'][:18] if len(miner['id']) > 18 else miner['id']
            balance = f"{miner['balance']:.4f}"
            hardware = miner['hardware'][:13] if len(miner['hardware']) > 13 else miner['hardware']
            
            message += f"{rank_icon:<5} {miner_id:<20} {balance:<12} {hardware:<15}\n"
        
        message += "```\n\n"
        
        # Architecture distribution
        arch_dist = self.calculate_architecture_distribution(miners)
        message += f"## 🖥️ Hardware Distribution\n"
        for arch, data in sorted(arch_dist.items(), key=lambda x: x[1]['count'], reverse=True):
            count = data['count']
            percent = data['percent']
            bar_length = int(percent / 5)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            message += f"**{arch}**: {bar} {percent:.1f}% ({count} miners)\n"
        message += "\n"
        
        # Rising star
        rising_star = self.find_rising_star(data)
        if rising_star:
            star = rising_star['miner']
            gain = rising_star['gain']
            message += f"## ⭐ Rising Star\n"
            message += f"**{star['id'][:20]}** gained **+{gain:.4f} RTC** since last update!\n"
            message += f"Current balance: **{star['balance']:.4f} RTC**\n\n"
        
        # Footer
        message += f"---\n"
        message += f"*Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n"
        message += f"*Next update in {self.config['frequency_hours']} hours*"
        
        return message
    
    def send_to_discord(self, message):
        """Send formatted message to Discord webhook"""
        if not self.webhook_url:
            print("Error: Discord webhook URL not configured")
            return False
        
        try:
            payload = {
                'content': message,
                'username': 'RustChain Leaderboard',
                'avatar_url': 'https://rustchain.org/logo.png'
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"✓ Leaderboard posted to Discord successfully")
            return True
        except Exception as e:
            print(f"Error posting to Discord: {e}")
            return False
    
    def run(self):
        """Main execution - generate and post leaderboard"""
        print(f"Fetching leaderboard data from {self.node_url}...")
        
        data = self.generate_leaderboard()
        if not data or not data['miners']:
            print("Error: No miner data available")
            return False
        
        print(f"Found {len(data['miners'])} miners")
        
        # Format message
        message = self.format_discord_message(data)
        
        # Save to cache
        self.cache['history'].append(data)
        # Keep only last 30 snapshots
        if len(self.cache['history']) > 30:
            self.cache['history'] = self.cache['history'][-30:]
        self.cache['last_run'] = datetime.utcnow().isoformat()
        self.save_cache()
        
        # Send to Discord
        return self.send_to_discord(message)

def main():
    """Entry point"""
    print("RustChain Leaderboard Bot")
    print("=" * 50)
    
    # Check for command line args
    if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
        print("DRY RUN MODE - Message will not be sent to Discord\n")
        bot = LeaderboardBot()
        data = bot.generate_leaderboard()
        if data:
            message = bot.format_discord_message(data)
            print(message)
        return
    
    # Normal run
    bot = LeaderboardBot()
    success = bot.run()
    
    if success:
        print("✓ Leaderboard update complete!")
        sys.exit(0)
    else:
        print("✗ Leaderboard update failed")
        sys.exit(1)

if __name__ == '__main__':
    main()
