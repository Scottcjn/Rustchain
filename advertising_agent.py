// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import random
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, render_template_string, request, jsonify
import requests
import threading
import sys
import os

DB_PATH = "advertising_posts.db"

class AdvertisingAgent:
    def __init__(self):
        self.platforms = {
            'bottube': {'url': 'https://bottube.ai', 'enabled': True, 'last_post': None},
            'moltbook': {'url': 'https://moltbook.com', 'enabled': True, 'last_post': None},
            '4claw': {'url': 'https://4claw.org', 'enabled': True, 'last_post': None},
            'agentchan': {'url': 'https://chan.alphakek.ai', 'enabled': True, 'last_post': None},
            'clawcities': {'url': 'https://clawcities.com', 'enabled': True, 'last_post': None},
            'agentgram': {'url': 'https://www.agentgram.co', 'enabled': True, 'last_post': None},
            'swarmhub': {'url': 'https://swarmhub.ai', 'enabled': True, 'last_post': None}
        }
        
        self.topics = [
            'RustChain mining opportunities',
            'BoTTube decentralized video platform',
            'Proof-of-Antiquity consensus innovation',
            'wRTC blockchain technology',
            'Beacon ecosystem development',
            'RTC token economics',
            'Decentralized mining rewards',
            'Agent-to-agent communication'
        ]
        
        self.content_templates = [
            "Exploring {topic} - the future of decentralized systems is here. Join the revolution! #RustChain #Blockchain",
            "Just discovered {topic} on RustChain. This technology is game-changing for Web3. Check it out!",
            "{topic} represents the next evolution in blockchain tech. RustChain is leading the way forward.",
            "The innovation behind {topic} is incredible. RustChain ecosystem continues to impress. #Crypto #Innovation",
            "Breaking: {topic} developments show massive potential. RustChain community growing strong! 🚀"
        ]
        
        self.min_interval = 300  # 5 minutes between posts
        self.max_interval = 1800  # 30 minutes max
        self.running = False
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    response_data TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS platform_config (
                    platform TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT 1,
                    api_key TEXT,
                    last_post DATETIME,
                    rate_limit INTEGER DEFAULT 300
                )
            ''')
    
    def generate_content(self) -> str:
        topic = random.choice(self.topics)
        template = random.choice(self.content_templates)
        return template.format(topic=topic)
    
    def can_post_to_platform(self, platform: str) -> bool:
        if not self.platforms[platform]['enabled']:
            return False
            
        last_post = self.platforms[platform]['last_post']
        if last_post is None:
            return True
            
        time_diff = datetime.now() - last_post
        return time_diff.total_seconds() > self.min_interval
    
    def log_post(self, platform: str, content: str, status: str = 'pending', response_data: str = None):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                'INSERT INTO posts (platform, content, status, response_data) VALUES (?, ?, ?, ?)',
                (platform, content, status, response_data)
            )
    
    def post_to_platform(self, platform: str, content: str) -> bool:
        try:
            # Simulate posting - replace with actual API calls
            platform_url = self.platforms[platform]['url']
            
            # Mock API call - implement actual platform APIs
            response = requests.post(
                f"{platform_url}/api/post",
                json={'content': content, 'type': 'promotional'},
                timeout=30,
                headers={'User-Agent': 'RustChain-AdvertisingAgent/1.0'}
            )
            
            success = response.status_code == 200
            status = 'success' if success else 'failed'
            
            self.log_post(platform, content, status, str(response.status_code))
            
            if success:
                self.platforms[platform]['last_post'] = datetime.now()
                logging.info(f"Posted to {platform}: {content[:50]}...")
            else:
                logging.error(f"Failed to post to {platform}: {response.status_code}")
                
            return success
            
        except Exception as e:
            logging.error(f"Error posting to {platform}: {str(e)}")
            self.log_post(platform, content, 'error', str(e))
            return False
    
    def run_posting_cycle(self):
        available_platforms = [p for p in self.platforms.keys() if self.can_post_to_platform(p)]
        
        if not available_platforms:
            logging.info("No platforms available for posting")
            return
        
        platform = random.choice(available_platforms)
        content = self.generate_content()
        
        logging.info(f"Attempting to post to {platform}")
        self.post_to_platform(platform, content)
    
    def daemon_loop(self):
        self.running = True
        logging.info("Advertising agent daemon started")
        
        while self.running:
            try:
                self.run_posting_cycle()
                sleep_time = random.randint(self.min_interval, self.max_interval)
                logging.info(f"Sleeping for {sleep_time} seconds")
                
                for _ in range(sleep_time):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logging.info("Received shutdown signal")
                break
            except Exception as e:
                logging.error(f"Error in daemon loop: {str(e)}")
                time.sleep(60)
        
        self.running = False
        logging.info("Advertising agent daemon stopped")
    
    def stop(self):
        self.running = False
    
    def get_stats(self) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM posts WHERE status = "success"')
            successful_posts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM posts WHERE status = "failed"')
            failed_posts = cursor.fetchone()[0]
            
            cursor.execute('SELECT platform, COUNT(*) FROM posts GROUP BY platform')
            platform_stats = dict(cursor.fetchall())
            
            cursor.execute('''
                SELECT platform, MAX(timestamp) 
                FROM posts WHERE status = "success" 
                GROUP BY platform
            ''')
            last_successful = dict(cursor.fetchall())
        
        return {
            'successful_posts': successful_posts,
            'failed_posts': failed_posts,
            'platform_stats': platform_stats,
            'last_successful': last_successful,
            'platforms_enabled': sum(1 for p in self.platforms.values() if p['enabled'])
        }

app = Flask(__name__)
agent = AdvertisingAgent()

@app.route('/')
def dashboard():
    stats = agent.get_stats()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>RustChain Advertising Agent</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { border-bottom: 2px solid #e0e0e0; padding-bottom: 20px; margin-bottom: 30px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card { background: #f8f9fa; padding: 20px; border-radius: 6px; text-align: center; }
            .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
            .platforms { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .platform-card { border: 1px solid #ddd; padding: 20px; border-radius: 6px; }
            .enabled { border-left: 4px solid #28a745; }
            .disabled { border-left: 4px solid #dc3545; }
            .controls { margin: 20px 0; }
            button { padding: 10px 20px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
            .btn-primary { background: #007bff; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .btn-success { background: #28a745; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 RustChain Advertising Agent</h1>
                <p>Autonomous multi-platform promotion system</p>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{{ stats.successful_posts }}</div>
                    <div>Successful Posts</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ stats.failed_posts }}</div>
                    <div>Failed Posts</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ stats.platforms_enabled }}</div>
                    <div>Active Platforms</div>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn-success" onclick="startAgent()">Start Agent</button>
                <button class="btn-danger" onclick="stopAgent()">Stop Agent</button>
                <button class="btn-primary" onclick="testPost()">Test Post</button>
                <button class="btn-primary" onclick="location.reload()">Refresh</button>
            </div>
            
            <h2>Platform Status</h2>
            <div class="platforms">
                {% for platform, config in platforms.items() %}
                <div class="platform-card {{ 'enabled' if config.enabled else 'disabled' }}">
                    <h3>{{ platform.title() }}</h3>
                    <p><strong>URL:</strong> {{ config.url }}</p>
                    <p><strong>Status:</strong> {{ 'Enabled' if config.enabled else 'Disabled' }}</p>
                    <p><strong>Posts:</strong> {{ stats.platform_stats.get(platform, 0) }}</p>
                    {% if stats.last_successful.get(platform) %}
                    <p><strong>Last Post:</strong> {{ stats.last_successful[platform] }}</p>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
        
        <script>
            function startAgent() {
                fetch('/start', {method: 'POST'})
                    .then(r => r.json())
                    .then(d => alert(d.message));
            }
            
            function stopAgent() {
                fetch('/stop', {method: 'POST'})
                    .then(r => r.json())
                    .then(d => alert(d.message));
            }
            
            function testPost() {
                fetch('/test', {method: 'POST'})
                    .then(r => r.json())
                    .then(d => alert(d.message));
            }
        </script>
    </body>
    </html>
    '''
    
    return render_template_string(html, stats=stats, platforms=agent.platforms)

@app.route('/start', methods=['POST'])
def start_agent():
    if not agent.running:
        thread = threading.Thread(target=agent.daemon_loop, daemon=True)
        thread.start()
        return jsonify({'message': 'Advertising agent started'})
    return jsonify({'message': 'Agent already running'})

@app.route('/stop', methods=['POST'])
def stop_agent():
    agent.stop()
    return jsonify({'message': 'Advertising agent stopped'})

@app.route('/test', methods=['POST'])
def test_post():
    try:
        agent.run_posting_cycle()
        return jsonify({'message': 'Test post completed - check logs'})
    except Exception as e:
        return jsonify({'message': f'Test failed: {str(e)}'})

@app.route('/api/stats')
def api_stats():
    return jsonify(agent.get_stats())

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('advertising_agent.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    if len(sys.argv) > 1 and sys.argv[1] == '--daemon':
        print("Starting advertising agent in daemon mode...")
        agent.daemon_loop()
    else:
        print("Starting Flask web interface...")
        app.run(host='0.0.0.0', port=5000, debug=False)