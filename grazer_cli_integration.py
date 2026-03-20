// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import logging
import json
from typing import Dict, List, Optional, Any

class DefensiveHandler:
    """Defensive error handling for platform API responses"""

    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def safe_get(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Safely get value from dict with logging"""
        try:
            return data.get(key, default)
        except Exception as e:
            self.logger.warning(f"Error accessing key '{key}': {e}")
            return default

    def safe_nested_get(self, data: Dict[str, Any], path: List[str], default: Any = None) -> Any:
        """Safely traverse nested dict path"""
        try:
            current = data
            for key in path:
                current = current.get(key, {})
                if not isinstance(current, dict) and key != path[-1]:
                    return default
            return current if current != {} else default
        except Exception as e:
            self.logger.warning(f"Error accessing nested path {path}: {e}")
            return default

class GrazerCLIIntegration:
    """CLI integration layer with defensive handlers for all platforms"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handler = DefensiveHandler(self.logger)

    def process_bottube_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process BoTTube discover response with defensive handling"""
        results = []
        videos = self.handler.safe_get(response_data, 'videos', [])

        for video in videos:
            processed = {
                'title': self.handler.safe_get(video, 'title', 'Unknown Title'),
                'author': self.handler.safe_get(video, 'author', 'Unknown Author'),
                'duration': self.handler.safe_get(video, 'duration', 'Unknown'),
                'views': self.handler.safe_get(video, 'views', '0'),
                'url': self.handler.safe_get(video, 'url', ''),
                'thumbnail': self.handler.safe_get(video, 'thumbnail', '')
            }
            results.append(processed)

        return results

    def process_moltbook_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process Moltbook discover response with defensive handling"""
        results = []
        posts = self.handler.safe_get(response_data, 'posts', [])

        for post in posts:
            processed = {
                'content': self.handler.safe_get(post, 'content', 'No content'),
                'author': self.handler.safe_get(post, 'author', 'Anonymous'),
                'timestamp': self.handler.safe_get(post, 'timestamp', ''),
                'likes': self.handler.safe_get(post, 'likes', '0'),
                'shares': self.handler.safe_get(post, 'shares', '0'),
                'comments_count': self.handler.safe_get(post, 'comments', '0'),
                'post_id': self.handler.safe_get(post, 'id', '')
            }
            results.append(processed)

        return results

    def process_clawsta_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process ClawSta discover response with defensive handling"""
        results = []
        images = self.handler.safe_get(response_data, 'images', [])

        for image in images:
            processed = {
                'caption': self.handler.safe_get(image, 'caption', 'No caption'),
                'username': self.handler.safe_get(image, 'username', 'unknown_user'),
                'image_url': self.handler.safe_get(image, 'image_url', ''),
                'thumbnail_url': self.handler.safe_get(image, 'thumbnail_url', ''),
                'likes_count': self.handler.safe_get(image, 'likes', '0'),
                'hashtags': self.handler.safe_get(image, 'hashtags', []),
                'location': self.handler.safe_get(image, 'location', ''),
                'posted_at': self.handler.safe_get(image, 'timestamp', '')
            }
            results.append(processed)

        return results

    def process_agentchan_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process AgentChan discover response with defensive handling"""
        results = []
        threads = self.handler.safe_get(response_data, 'threads', [])

        for thread in threads:
            processed = {
                'subject': self.handler.safe_get(thread, 'subject', 'No subject'),
                'author': self.handler.safe_get(thread, 'author', 'Anonymous'),
                'board': self.handler.safe_get(thread, 'board', 'unknown'),
                'reply_count': self.handler.safe_get(thread, 'replies', '0'),
                'last_bump': self.handler.safe_get(thread, 'last_bump', ''),
                'thread_id': self.handler.safe_get(thread, 'id', ''),
                'content_preview': self.handler.safe_get(thread, 'preview', 'No preview')
            }
            results.append(processed)

        return results

    def process_colony_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process Colony discover response with defensive handling"""
        results = []
        colonies = self.handler.safe_get(response_data, 'colonies', [])

        for colony in colonies:
            processed = {
                'name': self.handler.safe_get(colony, 'name', 'Unnamed Colony'),
                'description': self.handler.safe_get(colony, 'description', 'No description'),
                'member_count': self.handler.safe_get(colony, 'members', '0'),
                'category': self.handler.safe_get(colony, 'category', 'general'),
                'privacy': self.handler.safe_get(colony, 'privacy', 'public'),
                'created_date': self.handler.safe_get(colony, 'created', ''),
                'colony_id': self.handler.safe_get(colony, 'id', ''),
                'admin': self.handler.safe_get(colony, 'admin', 'Unknown Admin')
            }
            results.append(processed)

        return results

    def process_moltx_discover(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Process MoltX discover response with defensive handling"""
        results = []
        tweets = self.handler.safe_get(response_data, 'tweets', [])

        for tweet in tweets:
            user_data = self.handler.safe_get(tweet, 'user', {})

            processed = {
                'text': self.handler.safe_get(tweet, 'text', 'No content'),
                'username': self.handler.safe_get(user_data, 'username', 'unknown'),
                'display_name': self.handler.safe_get(user_data, 'display_name', 'Unknown User'),
                'retweet_count': self.handler.safe_get(tweet, 'retweets', '0'),
                'like_count': self.handler.safe_get(tweet, 'likes', '0'),
                'reply_count': self.handler.safe_get(tweet, 'replies', '0'),
                'created_at': self.handler.safe_get(tweet, 'created_at', ''),
                'tweet_id': self.handler.safe_get(tweet, 'id', ''),
                'verified': self.handler.safe_get(user_data, 'verified', False)
            }
            results.append(processed)

        return results

    def discover_command_router(self, platform: str, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Route discover commands to appropriate platform handler"""
        platform_handlers = {
            'bottube': self.process_bottube_discover,
            'moltbook': self.process_moltbook_discover,
            'clawsta': self.process_clawsta_discover,
            'agentchan': self.process_agentchan_discover,
            'colony': self.process_colony_discover,
            'moltx': self.process_moltx_discover
        }

        handler = platform_handlers.get(platform.lower())
        if not handler:
            self.logger.error(f"Unknown platform: {platform}")
            return []

        try:
            return handler(response_data)
        except Exception as e:
            self.logger.error(f"Error processing {platform} discover: {e}")
            return []

    def format_cli_output(self, results: List[Dict[str, str]], platform: str) -> str:
        """Format processed results for CLI output"""
        if not results:
            return f"No results found for {platform} discover command"

        output_lines = [f"\n=== {platform.upper()} DISCOVER RESULTS ==="]

        for i, item in enumerate(results, 1):
            output_lines.append(f"\n[{i}]")
            for key, value in item.items():
                if value and str(value) != '0':
                    output_lines.append(f"  {key}: {value}")

        output_lines.append(f"\nTotal results: {len(results)}\n")
        return "\n".join(output_lines)

def main():
    """Example usage of the integration layer"""
    integration = GrazerCLIIntegration()

    sample_data = {
        'posts': [
            {'content': 'Hello world', 'likes': '42'},
            {'author': 'user123'}
        ]
    }

    results = integration.discover_command_router('moltbook', sample_data)
    output = integration.format_cli_output(results, 'moltbook')
    print(output)

if __name__ == '__main__':
    main()
