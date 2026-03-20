// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import requests
from datetime import datetime

class DefensiveGrazerHandler:
    """Defensive error handling utilities for grazer platform APIs"""

    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 10

    def safe_get(self, data, key, default="N/A"):
        """Safely get value from dict with default fallback"""
        if isinstance(data, dict):
            return data.get(key, default)
        return default

    def safe_get_nested(self, data, keys, default="N/A"):
        """Safely get nested value from dict structure"""
        try:
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return default
                if current is None:
                    return default
            return current if current is not None else default
        except (KeyError, TypeError):
            return default

    def format_timestamp(self, timestamp, default="Unknown"):
        """Format timestamp safely"""
        if not timestamp or timestamp == "N/A":
            return default
        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            elif isinstance(timestamp, str):
                return timestamp
        except (ValueError, OSError):
            pass
        return default

    def discover_moltbook(self, query, limit=10):
        """Defensive Moltbook post discovery"""
        try:
            response = self.session.get(
                f"https://api.moltbook.social/posts/search",
                params={"q": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            posts = self.safe_get(data, "posts", [])
            results = []

            for post in posts:
                if not isinstance(post, dict):
                    continue

                result = {
                    "id": self.safe_get(post, "id"),
                    "author": self.safe_get(post, "author"),
                    "username": self.safe_get_nested(post, ["author_info", "username"]),
                    "content": self.safe_get(post, "content"),
                    "timestamp": self.format_timestamp(self.safe_get(post, "created_at")),
                    "likes": self.safe_get(post, "likes", 0),
                    "shares": self.safe_get(post, "reposts", 0),
                    "url": self.safe_get(post, "permalink"),
                    "verified": self.safe_get_nested(post, ["author_info", "verified"], False)
                }
                results.append(result)

            return {"status": "success", "count": len(results), "posts": results}

        except requests.RequestException as e:
            return {"status": "error", "message": f"Moltbook API error: {str(e)}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from Moltbook"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def discover_clawsta(self, query, limit=10):
        """Defensive ClawSta image discovery"""
        try:
            response = self.session.get(
                f"https://api.clawsta.net/images/search",
                params={"query": query, "count": limit}
            )
            response.raise_for_status()
            data = response.json()

            images = self.safe_get(data, "images", [])
            results = []

            for img in images:
                if not isinstance(img, dict):
                    continue

                result = {
                    "id": self.safe_get(img, "id"),
                    "title": self.safe_get(img, "title"),
                    "description": self.safe_get(img, "description"),
                    "url": self.safe_get(img, "url"),
                    "thumbnail": self.safe_get(img, "thumbnail_url"),
                    "width": self.safe_get(img, "width", 0),
                    "height": self.safe_get(img, "height", 0),
                    "creator": self.safe_get(img, "creator"),
                    "tags": self.safe_get(img, "tags", []),
                    "timestamp": self.format_timestamp(self.safe_get(img, "uploaded_at")),
                    "views": self.safe_get(img, "view_count", 0),
                    "likes": self.safe_get(img, "likes", 0)
                }
                results.append(result)

            return {"status": "success", "count": len(results), "images": results}

        except requests.RequestException as e:
            return {"status": "error", "message": f"ClawSta API error: {str(e)}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from ClawSta"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def discover_agentchan(self, query, board="all", limit=10):
        """Defensive AgentChan thread discovery"""
        try:
            response = self.session.get(
                f"https://api.agentchan.org/search",
                params={"q": query, "board": board, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            threads = self.safe_get(data, "threads", [])
            results = []

            for thread in threads:
                if not isinstance(thread, dict):
                    continue

                result = {
                    "id": self.safe_get(thread, "id"),
                    "title": self.safe_get(thread, "subject"),
                    "board": self.safe_get(thread, "board"),
                    "author": self.safe_get(thread, "name", "Anonymous"),
                    "content": self.safe_get(thread, "comment"),
                    "timestamp": self.format_timestamp(self.safe_get(thread, "time")),
                    "replies": self.safe_get(thread, "replies", 0),
                    "images": self.safe_get(thread, "images", 0),
                    "sticky": self.safe_get(thread, "sticky", False),
                    "locked": self.safe_get(thread, "locked", False),
                    "url": f"https://agentchan.org/{self.safe_get(thread, 'board')}/res/{self.safe_get(thread, 'id')}.html"
                }
                results.append(result)

            return {"status": "success", "count": len(results), "threads": results}

        except requests.RequestException as e:
            return {"status": "error", "message": f"AgentChan API error: {str(e)}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from AgentChan"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def discover_colony(self, query, limit=10):
        """Defensive Colony community discovery"""
        try:
            response = self.session.get(
                f"https://api.colony.network/communities/search",
                params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            communities = self.safe_get(data, "results", [])
            results = []

            for community in communities:
                if not isinstance(community, dict):
                    continue

                result = {
                    "id": self.safe_get(community, "id"),
                    "name": self.safe_get(community, "name"),
                    "description": self.safe_get(community, "description"),
                    "members": self.safe_get(community, "member_count", 0),
                    "creator": self.safe_get_nested(community, ["creator", "username"]),
                    "created": self.format_timestamp(self.safe_get(community, "created_at")),
                    "category": self.safe_get(community, "category"),
                    "private": self.safe_get(community, "is_private", False),
                    "verified": self.safe_get(community, "verified", False),
                    "url": f"https://colony.network/c/{self.safe_get(community, 'slug', self.safe_get(community, 'id'))}",
                    "avatar": self.safe_get(community, "avatar_url"),
                    "banner": self.safe_get(community, "banner_url")
                }
                results.append(result)

            return {"status": "success", "count": len(results), "communities": results}

        except requests.RequestException as e:
            return {"status": "error", "message": f"Colony API error: {str(e)}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from Colony"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    def discover_moltx(self, query, limit=10):
        """Defensive MoltX trading pair discovery"""
        try:
            response = self.session.get(
                f"https://api.moltx.exchange/pairs/search",
                params={"symbol": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            pairs = self.safe_get(data, "pairs", [])
            results = []

            for pair in pairs:
                if not isinstance(pair, dict):
                    continue

                result = {
                    "symbol": self.safe_get(pair, "symbol"),
                    "base": self.safe_get(pair, "base_currency"),
                    "quote": self.safe_get(pair, "quote_currency"),
                    "price": self.safe_get(pair, "last_price", "0"),
                    "volume_24h": self.safe_get(pair, "volume_24h", "0"),
                    "change_24h": self.safe_get(pair, "price_change_24h", "0"),
                    "high_24h": self.safe_get(pair, "high_24h", "0"),
                    "low_24h": self.safe_get(pair, "low_24h", "0"),
                    "market_cap": self.safe_get(pair, "market_cap"),
                    "active": self.safe_get(pair, "is_active", True),
                    "url": f"https://moltx.exchange/trade/{self.safe_get(pair, 'symbol', '').lower()}",
                    "updated": self.format_timestamp(self.safe_get(pair, "last_updated"))
                }
                results.append(result)

            return {"status": "success", "count": len(results), "pairs": results}

        except requests.RequestException as e:
            return {"status": "error", "message": f"MoltX API error: {str(e)}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from MoltX"}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

def create_defensive_handler():
    """Factory function to create defensive handler instance"""
    return DefensiveGrazerHandler()
