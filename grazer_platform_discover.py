// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import sys
from typing import Dict, List, Any, Optional

def safe_get_author(post: Dict[str, Any]) -> str:
    """Extract author info with fallback"""
    author = post.get('author', {})
    if isinstance(author, dict):
        return author.get('username', author.get('name', 'Unknown'))
    return str(author) if author else 'Unknown'

def safe_get_media(post: Dict[str, Any]) -> List[str]:
    """Extract media URLs with defensive handling"""
    media_list = []

    # Handle various media field names
    for field in ['images', 'media', 'attachments', 'files']:
        items = post.get(field, [])
        if not items:
            continue

        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    url = item.get('url', item.get('src', item.get('link', '')))
                    if url:
                        media_list.append(url)
                elif isinstance(item, str):
                    media_list.append(item)

    return media_list

def discover_moltbook(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Moltbook platform discover with defensive error handling"""
    posts = response_data.get('posts', response_data.get('data', []))
    if not isinstance(posts, list):
        posts = []

    processed_posts = []
    for post in posts:
        if not isinstance(post, dict):
            continue

        # Defensive field extraction
        post_data = {
            'id': post.get('id', post.get('post_id', 'unknown')),
            'content': post.get('content', post.get('text', post.get('body', ''))),
            'author': safe_get_author(post),
            'timestamp': post.get('timestamp', post.get('created_at', post.get('date', ''))),
            'likes': post.get('likes', post.get('reactions', {}).get('like', 0)),
            'shares': post.get('shares', post.get('reposts', 0)),
            'comments': post.get('comments', post.get('replies', [])),
            'media': safe_get_media(post)
        }
        processed_posts.append(post_data)

    return processed_posts

def discover_clawsta(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """ClawSta platform discover with defensive image handling"""
    items = response_data.get('items', response_data.get('posts', response_data.get('images', [])))
    if not isinstance(items, list):
        items = []

    processed_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # Safe image field extraction
        image_data = {
            'id': item.get('id', item.get('image_id', 'unknown')),
            'title': item.get('title', item.get('caption', item.get('description', ''))),
            'url': item.get('url', item.get('image_url', item.get('src', ''))),
            'thumbnail': item.get('thumbnail', item.get('thumb', item.get('preview', ''))),
            'width': item.get('width', item.get('w', 0)),
            'height': item.get('height', item.get('h', 0)),
            'size': item.get('size', item.get('file_size', 0)),
            'format': item.get('format', item.get('type', item.get('extension', 'unknown'))),
            'tags': item.get('tags', item.get('keywords', [])),
            'uploader': safe_get_author(item),
            'uploaded_at': item.get('uploaded_at', item.get('created', item.get('date', '')))
        }
        processed_items.append(image_data)

    return processed_items

def discover_agentchan(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """AgentChan platform discover with defensive handling"""
    threads = response_data.get('threads', response_data.get('posts', []))
    if not isinstance(threads, list):
        threads = []

    processed_threads = []
    for thread in threads:
        if not isinstance(thread, dict):
            continue

        # Extract thread data defensively
        thread_data = {
            'thread_id': thread.get('thread_id', thread.get('id', 'unknown')),
            'subject': thread.get('subject', thread.get('title', thread.get('topic', ''))),
            'op_post': thread.get('op', thread.get('original_post', {})),
            'replies': thread.get('replies', thread.get('responses', [])),
            'board': thread.get('board', thread.get('category', 'unknown')),
            'created': thread.get('created', thread.get('timestamp', '')),
            'last_reply': thread.get('last_reply', thread.get('updated', '')),
            'reply_count': thread.get('reply_count', len(thread.get('replies', []))),
            'is_sticky': thread.get('sticky', thread.get('pinned', False)),
            'is_locked': thread.get('locked', thread.get('closed', False))
        }

        # Process OP post if present
        op = thread_data.get('op_post', {})
        if isinstance(op, dict):
            thread_data['op_content'] = op.get('content', op.get('message', ''))
            thread_data['op_author'] = safe_get_author(op)
            thread_data['op_media'] = safe_get_media(op)

        processed_threads.append(thread_data)

    return processed_threads

def discover_colony(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Colony platform discover with defensive handling"""
    colonies = response_data.get('colonies', response_data.get('communities', response_data.get('groups', [])))
    if not isinstance(colonies, list):
        colonies = []

    processed_colonies = []
    for colony in colonies:
        if not isinstance(colony, dict):
            continue

        # Safe colony data extraction
        colony_data = {
            'id': colony.get('id', colony.get('colony_id', 'unknown')),
            'name': colony.get('name', colony.get('title', 'Unnamed Colony')),
            'description': colony.get('description', colony.get('about', '')),
            'member_count': colony.get('members', colony.get('member_count', 0)),
            'active_members': colony.get('active_members', colony.get('online', 0)),
            'category': colony.get('category', colony.get('type', 'general')),
            'is_private': colony.get('private', colony.get('is_private', False)),
            'created_date': colony.get('created', colony.get('established', '')),
            'rules': colony.get('rules', colony.get('guidelines', [])),
            'moderators': colony.get('moderators', colony.get('admins', [])),
            'recent_activity': colony.get('recent_posts', colony.get('activity', []))
        }
        processed_colonies.append(colony_data)

    return processed_colonies

def discover_moltx(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """MoltX platform discover with defensive handling"""
    exchanges = response_data.get('exchanges', response_data.get('transactions', response_data.get('trades', [])))
    if not isinstance(exchanges, list):
        exchanges = []

    processed_exchanges = []
    for exchange in exchanges:
        if not isinstance(exchange, dict):
            continue

        # Safe exchange data extraction
        exchange_data = {
            'id': exchange.get('id', exchange.get('transaction_id', 'unknown')),
            'type': exchange.get('type', exchange.get('transaction_type', 'unknown')),
            'amount': exchange.get('amount', exchange.get('value', 0)),
            'currency': exchange.get('currency', exchange.get('token', 'unknown')),
            'from_user': exchange.get('from', exchange.get('sender', 'unknown')),
            'to_user': exchange.get('to', exchange.get('recipient', 'unknown')),
            'timestamp': exchange.get('timestamp', exchange.get('created_at', '')),
            'status': exchange.get('status', exchange.get('state', 'unknown')),
            'fee': exchange.get('fee', exchange.get('transaction_fee', 0)),
            'hash': exchange.get('hash', exchange.get('tx_hash', '')),
            'confirmation_count': exchange.get('confirmations', 0),
            'block_height': exchange.get('block', exchange.get('block_number', 0))
        }
        processed_exchanges.append(exchange_data)

    return processed_exchanges

def discover_bottube(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """BoTTube platform discover with defensive handling (reference implementation)"""
    videos = response_data.get('videos', response_data.get('items', []))
    if not isinstance(videos, list):
        videos = []

    processed_videos = []
    for video in videos:
        if not isinstance(video, dict):
            continue

        video_data = {
            'id': video.get('id', 'unknown'),
            'title': video.get('title', ''),
            'description': video.get('description', ''),
            'duration': video.get('duration', 0),
            'views': video.get('view_count', video.get('views', 0)),
            'likes': video.get('like_count', video.get('likes', 0)),
            'dislikes': video.get('dislike_count', video.get('dislikes', 0)),
            'upload_date': video.get('upload_date', video.get('published_at', '')),
            'uploader': safe_get_author(video),
            'thumbnail': video.get('thumbnail', ''),
            'url': video.get('url', video.get('video_url', '')),
            'tags': video.get('tags', [])
        }
        processed_videos.append(video_data)

    return processed_videos

PLATFORM_HANDLERS = {
    'moltbook': discover_moltbook,
    'clawsta': discover_clawsta,
    'agentchan': discover_agentchan,
    'colony': discover_colony,
    'moltx': discover_moltx,
    'bottube': discover_bottube
}

def discover_platform_content(platform: str, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Main entry point for platform discovery with error handling"""
    if not isinstance(response_data, dict):
        print(f"Warning: Invalid response data for {platform}", file=sys.stderr)
        return []

    handler = PLATFORM_HANDLERS.get(platform.lower())
    if not handler:
        print(f"Warning: Unknown platform '{platform}'", file=sys.stderr)
        return []

    try:
        return handler(response_data)
    except Exception as e:
        print(f"Error processing {platform} data: {e}", file=sys.stderr)
        return []

def main():
    """CLI interface for testing platform discover methods"""
    if len(sys.argv) < 3:
        print("Usage: python grazer_platform_discover.py <platform> <json_file>")
        print("Available platforms:", ', '.join(PLATFORM_HANDLERS.keys()))
        sys.exit(1)

    platform = sys.argv[1]
    json_file = sys.argv[2]

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        results = discover_platform_content(platform, data)
        print(json.dumps(results, indent=2))

    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{json_file}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
