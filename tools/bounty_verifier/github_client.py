"""
GitHub API client for bounty verification.
Handles rate limiting, authentication, and API calls.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import ClaimComment


class RateLimitExceeded(Exception):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubClient:
    """GitHub API client with rate limiting and caching."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(
        self,
        token: str,
        owner: str = "Scottcjn",
        repo: str = "rustchain-bounties",
        rate_limit_buffer: int = 100,
    ):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.rate_limit_buffer = rate_limit_buffer
        
        # Rate limiting state
        self._rate_limit_remaining = 1000
        self._rate_limit_reset: Optional[datetime] = None
        self._request_count = 0
        self._last_request_time: Optional[float] = None
        
        # Cache for expensive operations
        self._following_cache: Dict[str, Tuple[bool, float]] = {}
        self._star_count_cache: Dict[str, Tuple[int, float]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"rustchain-bounty-verifier/1.0.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def _check_rate_limit(self) -> None:
        """Check if we're within rate limits."""
        if self._rate_limit_reset and datetime.utcnow() < self._rate_limit_reset:
            if self._rate_limit_remaining <= self.rate_limit_buffer:
                wait_time = (self._rate_limit_reset - datetime.utcnow()).total_seconds()
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Reset in {wait_time:.0f}s. "
                    f"Remaining: {self._rate_limit_remaining}"
                )
    
    def _update_rate_limit(self, response_headers: Dict[str, str]) -> None:
        """Update rate limit state from response headers."""
        try:
            self._rate_limit_remaining = int(response_headers.get("x-ratelimit-remaining", 1000))
            reset_ts = int(response_headers.get("x-ratelimit-reset", 0))
            if reset_ts:
                self._rate_limit_reset = datetime.fromtimestamp(reset_ts)
        except (ValueError, TypeError):
            pass
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retries: int = 3,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, str]]:
        """Make a GitHub API request with retry logic."""
        self._check_rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()
        
        body = None
        if data and method in ("POST", "PATCH", "PUT"):
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        
        req = Request(url, data=body, headers=headers, method=method)
        
        last_error: Optional[Exception] = None
        for attempt in range(retries):
            try:
                with urlopen(req, timeout=30) as response:
                    response_headers = dict(response.headers)
                    self._update_rate_limit(response_headers)
                    
                    if response.status == 204:  # No content
                        return None, response_headers
                    
                    content = response.read()
                    if content:
                        return json.loads(content.decode("utf-8")), response_headers
                    return None, response_headers
                    
            except HTTPError as e:
                last_error = e
                if e.code == 403:
                    # Rate limited
                    self._rate_limit_remaining = 0
                    raise RateLimitExceeded(f"Rate limited: {e}")
                elif e.code >= 500:
                    # Server error, retry
                    time.sleep(2 ** attempt)
                    continue
                else:
                    # Client error, don't retry
                    break
            except URLError as e:
                last_error = e
                time.sleep(2 ** attempt)
                continue
        
        if last_error:
            raise last_error
        return None, {}
    
    def get_issue_comments(
        self,
        issue_number: int,
        per_page: int = 100,
    ) -> List[ClaimComment]:
        """Get all comments for an issue."""
        endpoint = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments"
        comments = []
        page = 1
        
        while True:
            data, _ = self._request("GET", f"{endpoint}?page={page}&per_page={per_page}")
            if not data:
                break
            
            for comment_data in data:
                comment = ClaimComment.from_github_api(comment_data, issue_number)
                comments.append(comment)
            
            if len(data) < per_page:
                break
            page += 1
        
        return comments
    
    def check_following(self, follower: str, target: Optional[str] = None) -> bool:
        """Check if a user is following the target user."""
        target = target or self.owner
        
        # Check cache
        cache_key = f"{follower}:{target}"
        if cache_key in self._following_cache:
            result, timestamp = self._following_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return result
        
        # Check if user exists first
        user_data, _ = self._request("GET", f"/users/{follower}")
        if not user_data:
            return False
        
        # Check following status
        try:
            self._request(
                "GET",
                f"/users/{follower}/following/{target}"
            )
            # 204 No Content means following (successful return), 404 raises HTTPError
            is_following = True
        except HTTPError as e:
            if e.code == 404:
                is_following = False
            else:
                raise
        
        # Cache result
        self._following_cache[cache_key] = (is_following, time.time())
        return is_following
    
    def get_starred_repos_count(self, user: str, owner: Optional[str] = None) -> int:
        """Get count of user's starred repos owned by specific owner."""
        owner = owner or self.owner
        
        # Check cache
        cache_key = f"{user}:{owner}"
        if cache_key in self._star_count_cache:
            count, timestamp = self._star_count_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return count
        
        # Count starred repos
        count = 0
        page = 1
        
        while True:
            data, _ = self._request(
                "GET",
                f"/users/{user}/starred?per_page=100&page={page}"
            )
            if not data:
                break
            
            for repo in data:
                if repo.get("owner", {}).get("login") == owner:
                    count += 1
            
            if len(data) < 100:
                break
            page += 1
        
        # Cache result
        self._star_count_cache[cache_key] = (count, time.time())
        return count
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information."""
        data, _ = self._request("GET", f"/users/{username}")
        return data
    
    def post_comment(self, issue_number: int, body: str) -> Optional[Dict[str, Any]]:
        """Post a comment to an issue."""
        data, _ = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments",
            data={"body": body},
        )
        return data
    
    def update_comment(self, comment_id: int, body: str) -> Optional[Dict[str, Any]]:
        """Update an existing comment."""
        data, _ = self._request(
            "PATCH",
            f"/repos/{self.owner}/{self.repo}/issues/comments/{comment_id}",
            data={"body": body},
        )
        return data
    
    def get_issue(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get issue details."""
        data, _ = self._request("GET", f"/repos/{self.owner}/{self.repo}/issues/{issue_number}")
        return data
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        data, _ = self._request("GET", "/rate_limit")
        return data or {}
