// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import requests
import time
import json
import logging
import random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
import threading
import os

DB_PATH = 'rustchain.db'

class MultiPlatformAgent:
    def __init__(self):
        self.platforms = {
            'bottube': {'url': 'https://bottube.ai', 'last_post': None, 'rate_limit': 3600},
            'moltbook': {'url': 'https://moltbook.com', 'last_post': None, 'rate_limit': 1800},
            '4claw': {'url': 'https://4claw.org', 'last_post': None, 'rate_limit': 7200},
            'agentchan': {'url': 'https://chan.alphakek.ai', 'last_post': None, 'rate_limit': 3600},
            'clawcities': {'url': 'https://clawcities.com', 'last_post': None, 'rate_limit': 14400},
            'agentgram': {'url': 'https://agentgram.co', 'last_post': None, 'rate_limit': 1800},
            'swarmhub': {'url': 'https://swarmhub.ai', 'last_post': None, 'rate_limit': 3600}
        }
        
        self.content_templates = [
            "🚀 RustChain: Next-gen blockchain with Rust performance. Secure, fast, scalable. {link}",
            "⚡ Experience true blockchain speed with RustChain. Built for enterprise. {link}",
            "🔗 RustChain delivers enterprise-grade blockchain solutions. Memory-safe. Lightning-fast. {link}",
            "💎 Discover RustChain: Where blockchain meets Rust's power and safety. {link}",
            "🛡️ RustChain - Secure blockchain infrastructure built with Rust. Zero-cost abstractions. {link}",
            "⚙️ Revolutionary blockchain tech: RustChain combines speed, security, scalability. {link}",
            "🌟 RustChain: Professional blockchain platform for serious applications. {link}"
        ]
        
        self.links = [
            "https://github.com/Scottcjn/Rustchain",
            "https://rustchain.dev",
            "https://beacon-network.io"
        ]
        
        self.dry_run = False
        self.running = False
        self.init_db()
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('agent.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT FALSE,
                    response TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS platform_config (
                    platform TEXT PRIMARY KEY,
                    api_key TEXT,
                    username TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    last_post_time DATETIME
                )
            ''')
            
    def can_post_to_platform(self, platform):
        rate_limit = self.platforms[platform]['rate_limit']
        last_post = self.platforms[platform]['last_post']
        
        if not last_post:
            return True
            
        time_diff = (datetime.now() - last_post).total_seconds()
        return time_diff >= rate_limit
        
    def generate_content(self):
        template = random.choice(self.content_templates)
        link = random.choice(self.links)
        return template.format(link=link)
        
    def post_to_platform(self, platform, content):
        if self.dry_run:
            self.logger.info(f"DRY RUN - Would post to {platform}: {content[:50]}...")
            success = True
            response = "Dry run - not posted"
        else:
            success, response = self.actual_platform_post(platform, content)
            
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO posts (platform, content, success, response) VALUES (?, ?, ?, ?)',
                (platform, content, success, response)
            )
            
        if success:
            self.platforms[platform]['last_post'] = datetime.now()
            
        return success, response
        
    def actual_platform_post(self, platform, content):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.execute(
                    'SELECT api_key, username FROM platform_config WHERE platform = ?',
                    (platform,)
                )
                config = cursor.fetchone()
                
            if not config:
                return False, "No configuration found"
                
            api_key, username = config
            
            if platform == 'bottube':
                return self.post_bottube(content, api_key, username)
            elif platform == 'moltbook':
                return self.post_moltbook(content, api_key, username)
            elif platform == '4claw':
                return self.post_4claw(content, api_key, username)
            elif platform == 'agentchan':
                return self.post_agentchan(content, api_key, username)
            elif platform == 'clawcities':
                return self.post_clawcities(content, api_key, username)
            elif platform == 'agentgram':
                return self.post_agentgram(content, api_key, username)
            elif platform == 'swarmhub':
                return self.post_swarmhub(content, api_key, username)
                
            return False, "Unknown platform"
            
        except Exception as e:
            self.logger.error(f"Error posting to {platform}: {str(e)}")
            return False, str(e)
            
    def post_bottube(self, content, api_key, username):
        headers = {'Authorization': f'Bearer {api_key}'}
        data = {'content': content, 'type': 'comment'}
        
        try:
            response = requests.post(
                f"{self.platforms['bottube']['url']}/api/post",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)
            
    def post_moltbook(self, content, api_key, username):
        headers = {'X-API-Key': api_key}
        data = {'text': content, 'submolt': 'blockchain'}
        
        try:
            response = requests.post(
                f"{self.platforms['moltbook']['url']}/api/posts",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code in [200, 201], response.text
        except Exception as e:
            return False, str(e)
            
    def post_4claw(self, content, api_key, username):
        headers = {'Authorization': api_key}
        data = {'body': content, 'board': 'tech', 'subject': 'RustChain Update'}
        
        try:
            response = requests.post(
                f"{self.platforms['4claw']['url']}/api/threads",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code in [200, 201], response.text
        except Exception as e:
            return False, str(e)
            
    def post_agentchan(self, content, api_key, username):
        data = {'message': content, 'board': 'blockchain', 'api_key': api_key}
        
        try:
            response = requests.post(
                f"{self.platforms['agentchan']['url']}/post",
                data=data,
                timeout=30
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)
            
    def post_clawcities(self, content, api_key, username):
        headers = {'X-Auth-Token': api_key}
        data = {'content': content, 'city': 'tech-hub'}
        
        try:
            response = requests.post(
                f"{self.platforms['clawcities']['url']}/api/presence",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)
            
    def post_agentgram(self, content, api_key, username):
        headers = {'Authorization': f'Token {api_key}'}
        data = {'text': content, 'hashtags': ['#blockchain', '#rustchain']}
        
        try:
            response = requests.post(
                f"{self.platforms['agentgram']['url']}/api/posts",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code in [200, 201], response.text
        except Exception as e:
            return False, str(e)
            
    def post_swarmhub(self, content, api_key, username):
        headers = {'X-API-Key': api_key}
        data = {'message': content, 'channel': 'blockchain-projects'}
        
        try:
            response = requests.post(
                f"{self.platforms['swarmhub']['url']}/api/messages",
                headers=headers,
                json=data,
                timeout=30
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)
            
    def run_posting_cycle(self):
        self.logger.info("Starting posting cycle")
        
        available_platforms = [
            platform for platform in self.platforms.keys()
            if self.can_post_to_platform(platform) and self.is_platform_enabled(platform)
        ]
        
        if not available_platforms:
            self.logger.info("No platforms available for posting")
            return
            
        platform = random.choice(available_platforms)
        content = self.generate_content()
        
        self.logger.info(f"Posting to {platform}")
        success, response = self.post_to_platform(platform, content)
        
        if success:
            self.logger.info(f"Successfully posted to {platform}")
        else:
            self.logger.error(f"Failed to post to {platform}: {response}")
            
    def is_platform_enabled(self, platform):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                'SELECT enabled FROM platform_config WHERE platform = ?',
                (platform,)
            )
            result = cursor.fetchone()
            return result and result[0]
            
    def start_daemon(self, interval=3600):
        self.running = True
        self.logger.info(f"Starting agent daemon with {interval}s interval")
        
        while self.running:
            try:
                self.run_posting_cycle()
                time.sleep(interval + random.randint(-300, 300))  # Add jitter
            except KeyboardInterrupt:
                self.logger.info("Stopping agent daemon")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error in daemon loop: {str(e)}")
                time.sleep(60)
                
    def stop_daemon(self):
        self.running = False
        
    def get_stats(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT platform, COUNT(*) as total, 
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                       MAX(timestamp) as last_post
                FROM posts 
                GROUP BY platform
            ''')
            return cursor.fetchall()

app = Flask(__name__)
agent = MultiPlatformAgent()

@app.route('/')
def dashboard():
    stats = agent.get_stats()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Multi-Platform Agent</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #1a1a1a; color: #fff; }
            .header { border-bottom: 2px solid #ff6b35; padding-bottom: 20px; margin-bottom: 30px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .platform { background: #2a2a2a; padding: 20px; border-radius: 8px; border-left: 4px solid #ff6b35; }
            .controls { margin: 30px 0; }
            .btn { background: #ff6b35; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
            .btn:hover { background: #e55a2b; }
            .status { color: #4ade80; }
            .error { color: #ef4444; }
            .config-form { background: #2a2a2a; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .form-group { margin: 15px 0; }
            .form-group label { display: block; margin-bottom: 5px; }
            .form-group input { width: 100%; padding: 8px; background: #1a1a1a; border: 1px solid #444; color: #fff; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 RustChain Multi-Platform Agent</h1>
            <p>Professional blockchain promotion across agent platforms</p>
        </div>
        
        <div class="controls">
            <button class="btn" onclick="toggleAgent()">{{ 'Stop' if agent.running else 'Start' }} Agent</button>
            <button class="btn" onclick="testPost()">Test Post</button>
            <button class="btn" onclick="toggleDryRun()">{{ 'Disable' if agent.dry_run else 'Enable' }} Dry Run</button>
        </div>
        
        <div class="stats">
            {% for platform_stats in stats %}
            <div class="platform">
                <h3>{{ platform_stats[0].title() }}</h3>
                <p>Total Posts: {{ platform_stats[1] }}</p>
                <p>Successful: {{ platform_stats[2] }}</p>
                <p>Success Rate: {{ "%.1f" | format((platform_stats[2] / platform_stats[1] * 100) if platform_stats[1] > 0 else 0) }}%</p>
                <p>Last Post: {{ platform_stats[3] or 'Never' }}</p>
            </div>
            {% endfor %}
        </div>
        
        <div class="config-form">
            <h3>Platform Configuration</h3>
            <div class="form-group">
                <label>Platform:</label>
                <select id="platform" style="width: 100%; padding: 8px; background: #1a1a1a; border: 1px solid #444; color: #fff;">
                    <option value="bottube">BoTTube</option>
                    <option value="moltbook">Moltbook</option>
                    <option value="4claw">4Claw</option>
                    <option value="agentchan">AgentChan</option>
                    <option value="clawcities">ClawCities</option>
                    <option value="agentgram">AgentGram</option>
                    <option value="swarmhub">SwarmHub</option>
                </select>
            </div>
            <div class="form-group">
                <label>API Key:</label>
                <input type="text" id="apiKey" placeholder="Enter API key">
            </div>
            <div class="form-group">
                <label>Username:</label>
                <input type="text" id="username" placeholder="Enter username">
            </div>
            <button class="btn" onclick="saveConfig()">Save Configuration</button>
        </div>
        
        <script>
            function toggleAgent() {
                fetch('/toggle_agent', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        location.reload();
                    });
            }
            
            function testPost() {
                fetch('/test_post', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message);
                    });
            }
            
            function toggleDryRun() {
                fetch('/toggle_dry_run', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        location.reload();
                    });
            }
            
            function saveConfig() {
                const platform = document.getElementById('platform').value;
                const apiKey = document.getElementById('apiKey').value;
                const username = document.getElementById('username').value;
                
                fetch('/save_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({platform, apiKey, username})
                }).then(r => r.json()).then(data => {
                    alert(data.message);
                });
            }
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(html, stats=stats, agent=agent)

@app.route('/toggle_agent', methods=['POST'])
def toggle_agent():
    if agent.running:
        agent.stop_daemon()
        return jsonify({'status': 'stopped'})
    else:
        threading.Thread(target=agent.start_daemon, daemon=True).start()
        return jsonify({'status': 'started'})

@app.route('/test_post', methods=['POST'])
def test_post():
    try:
        agent.run_posting_cycle()
        return jsonify({'message': 'Test post completed. Check logs for results.'})
    except Exception as e:
        return jsonify({'message': f'Test failed: {str(e)}'})

@app.route('/toggle_dry_run', methods=['POST'])
def toggle_dry_run():
    agent.dry_run = not agent.dry_run
    return jsonify({'dry_run': agent.dry_run})

@app.route('/save_config', methods=['POST'])
def save_config():
    data = request.get_json()
    platform = data['platform']
    api_key = data['apiKey']
    username = data['username']
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT OR REPLACE INTO platform_config (platform, api_key, username, enabled)
            VALUES (?, ?, ?, TRUE)
        ''', (platform, api_key, username))
    
    return jsonify({'message': f'Configuration saved for {platform}'})

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'daemon':
        agent.dry_run = '--dry-run' in sys.argv
        interval = 3600
        
        if '--interval' in sys.argv:
            idx = sys.argv.index('--interval')
            if idx + 1 < len(sys.argv):
                interval = int(sys.argv[idx + 1])
        
        agent.start_daemon(interval)
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)