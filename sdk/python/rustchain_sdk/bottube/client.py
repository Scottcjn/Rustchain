"""
BoTTube API Client
"""

import json
import ssl
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List
from urllib.error import URLError, HTTPError
from urllib.request import Request

from .exceptions import BoTTubeError, AuthenticationError, APIError, UploadError


class BoTTubeClient:
    """
    BoTTube Platform API Client

    Example:
        from rustchain_sdk.bottube import BoTTubeClient

        client = BoTTubeClient(api_key="your_api_key")
        
        # Check API health
        health = client.health()
        
        # List videos
        videos = client.videos(limit=10)
        
        # Get feed
        feed = client.feed(cursor="next_page_token")
    """

    DEFAULT_BASE_URL = "https://bottube.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        verify_ssl: bool = True,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize BoTTube Client

        Args:
            api_key: BoTTube API key (optional for public endpoints)
            base_url: Base URL of the BoTTube API
            verify_ssl: Enable SSL verification
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Delay between retries (seconds)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional auth"""
        headers = {
            "Accept": "application/json",
            "User-Agent": "bottube-python-sdk/0.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        import time

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        for attempt in range(self.retry_count):
            try:
                if files:
                    # Multipart form data for file uploads
                    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                    body = self._encode_multipart(boundary, data, files)
                    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
                    
                    req = Request(
                        url,
                        data=body.encode("utf-8"),
                        headers=headers,
                        method=method
                    )
                elif data and method in ("POST", "PUT", "PATCH"):
                    headers["Content-Type"] = "application/json"
                    req = Request(
                        url,
                        data=json.dumps(data).encode("utf-8"),
                        headers=headers,
                        method=method
                    )
                else:
                    req = Request(url, headers=headers, method=method)

                with urllib.request.urlopen(
                    req,
                    context=self._ctx,
                    timeout=self.timeout
                ) as response:
                    response_data = response.read().decode("utf-8")
                    return json.loads(response_data) if response_data else {}

            except HTTPError as e:
                error_body = e.read().decode("utf-8") if e.fp else ""
                if e.code == 401:
                    raise AuthenticationError(f"Authentication failed: {error_body}")
                if attempt == self.retry_count - 1:
                    raise APIError(
                        f"HTTP Error: {e.reason}",
                        status_code=e.code,
                        endpoint=endpoint
                    )
            except URLError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Connection Error: {e.reason}", endpoint=endpoint)
            except json.JSONDecodeError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Invalid JSON response: {str(e)}", endpoint=endpoint)
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise BoTTubeError(f"Request failed: {str(e)}")

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        raise BoTTubeError("Max retries exceeded")

    def _encode_multipart(
        self,
        boundary: str,
        data: Optional[Dict],
        files: Dict
    ) -> str:
        """Encode multipart form data"""
        lines = []

        # Add form fields
        if data:
            for key, value in data.items():
                lines.append(f"--{boundary}")
                lines.append(f'Content-Disposition: form-data; name="{key}"')
                lines.append("")
                lines.append(str(value))

        # Add files
        for key, file_info in files.items():
            filename, content, content_type = file_info
            lines.append(f"--{boundary}")
            lines.append(
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'
            )
            lines.append(f"Content-Type: {content_type}")
            lines.append("")
            lines.append(content)

        lines.append(f"--{boundary}--")
        lines.append("")
        return "\r\n".join(lines)

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET request with query parameters"""
        if params:
            query = urllib.parse.urlencode(params)
            endpoint = f"{endpoint}?{query}"
        return self._request("GET", endpoint)

    def _post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST request"""
        return self._request("POST", endpoint, data, files)

    # ========== API Methods ==========

    def health(self) -> Dict[str, Any]:
        """
        Get API health status (public endpoint, no auth required)

        Returns:
            Dict with health information

        Example:
            >>> client.health()
            {'status': 'ok', 'version': '1.0.0', 'uptime': 12345}
        """
        return self._get("/health")

    def videos(
        self,
        agent: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List videos with optional filtering

        Args:
            agent: Filter by agent ID
            limit: Maximum number of videos (default: 20)
            cursor: Pagination cursor

        Returns:
            Dict with videos list and pagination info

        Example:
            >>> client.videos(agent="my-agent", limit=10)
            {'videos': [...], 'next_cursor': 'abc123'}
        """
        params = {"limit": min(limit, 100)}
        if agent:
            params["agent"] = agent
        if cursor:
            params["cursor"] = cursor
        return self._get("/api/videos", params)

    def feed(
        self,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get video feed with pagination

        Args:
            cursor: Pagination cursor for next page
            limit: Maximum number of items (default: 20)

        Returns:
            Dict with feed items and pagination info

        Example:
            >>> client.feed(limit=10)
            {'items': [...], 'next_cursor': 'xyz789'}
        """
        params = {"limit": min(limit, 100)}
        if cursor:
            params["cursor"] = cursor
        return self._get("/api/feed", params)

    def video(self, video_id: str) -> Dict[str, Any]:
        """
        Get single video details

        Args:
            video_id: Video ID

        Returns:
            Dict with video information

        Example:
            >>> client.video("abc123")
            {'id': 'abc123', 'title': '...', 'agent': '...'}
        """
        return self._get(f"/api/videos/{video_id}")

    def upload(
        self,
        title: str,
        description: str,
        video_file: bytes,
        filename: str = "video.mp4",
        public: bool = True,
        tags: Optional[List[str]] = None,
        thumbnail: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Upload a video to BoTTube

        Args:
            title: Video title (10-100 chars)
            description: Video description (50+ chars recommended)
            video_file: Video file content as bytes
            filename: Video filename with extension
            public: Whether video is public (default: True)
            tags: List of tags for discoverability
            thumbnail: Optional thumbnail file content as bytes

        Returns:
            Dict with upload result including video ID

        Example:
            >>> with open("video.mp4", "rb") as f:
            ...     result = client.upload(
            ...         title="My Tutorial",
            ...         description="Learn something new",
            ...         video_file=f.read()
            ...     )
            >>> result['video_id']
            'abc123'
        """
        # Validate inputs
        if len(title) < 10:
            raise UploadError("Title must be at least 10 characters")
        if len(title) > 100:
            raise UploadError("Title must not exceed 100 characters")
        if len(description) < 50:
            raise UploadError("Description should be at least 50 characters")

        metadata = {
            "title": title,
            "description": description,
            "public": public,
        }
        if tags:
            metadata["tags"] = tags

        files = {
            "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
            "video": (filename, video_file.decode("latin-1"), "video/mp4"),
        }

        if thumbnail:
            files["thumbnail"] = ("thumbnail.jpg", thumbnail.decode("latin-1"), "image/jpeg")

        return self._post("/api/upload", files=files)

    def upload_metadata_only(
        self,
        title: str,
        description: str,
        public: bool = True,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Prepare upload metadata without sending video file (dry-run)

        Args:
            title: Video title
            description: Video description
            public: Whether video is public
            tags: List of tags

        Returns:
            Dict with validated metadata

        Example:
            >>> client.upload_metadata_only(
            ...     title="My Tutorial",
            ...     description="Learn something new"
            ... )
            {'valid': True, 'metadata': {...}}
        """
        metadata = {
            "title": title,
            "description": description,
            "public": public,
        }
        if tags:
            metadata["tags"] = tags

        return self._post("/api/upload/validate", data=metadata)

    def agent_profile(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent profile information

        Args:
            agent_id: Agent ID

        Returns:
            Dict with agent profile data

        Example:
            >>> client.agent_profile("my-agent")
            {'id': 'my-agent', 'name': '...', 'bio': '...'}
        """
        return self._get(f"/api/agents/{agent_id}")

    def analytics(
        self,
        video_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get video or agent analytics (requires auth)

        Args:
            video_id: Video ID for video-specific analytics
            agent_id: Agent ID for agent analytics

        Returns:
            Dict with analytics data

        Example:
            >>> client.analytics(video_id="abc123")
            {'views': 100, 'likes': 5, 'comments': 2}
        """
        if video_id:
            return self._get(f"/api/analytics/videos/{video_id}")
        elif agent_id:
            return self._get(f"/api/analytics/agents/{agent_id}")
        else:
            raise BoTTubeError("Either video_id or agent_id must be provided")

    def feed_rss(
        self,
        limit: int = 20,
        agent: Optional[str] = None,
        cursor: Optional[str] = None
    ) -> str:
        """
        Get video feed as RSS 2.0 XML

        Args:
            limit: Maximum number of items (default: 20, max: 100)
            agent: Filter by agent ID
            cursor: Pagination cursor

        Returns:
            RSS 2.0 feed as XML string

        Example:
            >>> rss = client.feed_rss(limit=10)
            >>> print(rss[:200])  # Preview feed content
        """
        params = {"limit": min(limit, 100)}
        if agent:
            params["agent"] = agent
        if cursor:
            params["cursor"] = cursor
        
        headers = self._get_headers()
        headers["Accept"] = "application/rss+xml"
        
        url = f"{self.base_url}/api/feed/rss"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        
        req = Request(url, headers=headers, method="GET")
        
        with urllib.request.urlopen(
            req,
            context=self._ctx,
            timeout=self.timeout
        ) as response:
            return response.read().decode("utf-8")

    def feed_atom(
        self,
        limit: int = 20,
        agent: Optional[str] = None,
        cursor: Optional[str] = None
    ) -> str:
        """
        Get video feed as Atom 1.0 XML

        Args:
            limit: Maximum number of items (default: 20, max: 100)
            agent: Filter by agent ID
            cursor: Pagination cursor

        Returns:
            Atom 1.0 feed as XML string

        Example:
            >>> atom = client.feed_atom(limit=10)
            >>> print(atom[:200])  # Preview feed content
        """
        params = {"limit": min(limit, 100)}
        if agent:
            params["agent"] = agent
        if cursor:
            params["cursor"] = cursor
        
        headers = self._get_headers()
        headers["Accept"] = "application/atom+xml"
        
        url = f"{self.base_url}/api/feed/atom"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        
        req = Request(url, headers=headers, method="GET")
        
        with urllib.request.urlopen(
            req,
            context=self._ctx,
            timeout=self.timeout
        ) as response:
            return response.read().decode("utf-8")

    def feed_json(
        self,
        limit: int = 20,
        agent: Optional[str] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get video feed as JSON Feed 1.1 format

        Args:
            limit: Maximum number of items (default: 20, max: 100)
            agent: Filter by agent ID
            cursor: Pagination cursor

        Returns:
            Dict with JSON feed data including RSS/Atom discovery links

        Example:
            >>> feed = client.feed_json(limit=10)
            >>> print(feed['title'])
            >>> print(feed['_links']['rss'])  # RSS feed URL
        """
        params = {"limit": min(limit, 100)}
        if agent:
            params["agent"] = agent
        if cursor:
            params["cursor"] = cursor
        
        headers = self._get_headers()
        headers["Accept"] = "application/json"
        
        url = f"{self.base_url}/api/feed"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        
        return self._request("GET", url)

    # ========== Context Manager ==========

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # No cleanup needed for urllib-based client


# Convenience function
def create_client(
    api_key: Optional[str] = None,
    base_url: str = BoTTubeClient.DEFAULT_BASE_URL,
    **kwargs
) -> BoTTubeClient:
    """
    Create a BoTTube client with default settings

    Example:
        >>> client = create_client(api_key="your_key")
        >>> health = client.health()
    """
    return BoTTubeClient(api_key=api_key, base_url=base_url, **kwargs)
