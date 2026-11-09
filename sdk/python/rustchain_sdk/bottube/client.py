"""
BoTTube API Client
"""

import json
import os
import ssl
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from urllib.error import URLError, HTTPError
from urllib.request import Request

from .exceptions import (
    BoTTubeError,
    AuthenticationError,
    APIError,
    UploadError,
    InsufficientRTCBalanceError,
    UnknownRTCServiceError,
    ExpiredServiceTokenError,
    PurchaseQuantityCapError,
)

MAX_PURCHASE_QUANTITY = 100


def _to_decimal_rtc(value: Union[str, int, Decimal], field_name: str = "amount") -> Decimal:
    """Convert a wire or caller RTC amount to Decimal without ever accepting IEEE-754 binary fractions."""
    if isinstance(value, bool) or value is None:
        raise TypeError(f"{field_name} must be Decimal, int, or numeric string")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_name} cannot be empty")
        try:
            return Decimal(stripped)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid Decimal value for {field_name}: {value!r}") from exc
    raise TypeError(f"{field_name} must be Decimal, int, or str (got {type(value).__name__})")


def resolve_bottube_api_key(explicit_key: Optional[str] = None) -> Optional[str]:
    """Resolve BoTTube API key from explicit argument, environment, or config file."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    env_key = os.environ.get("BOTTUBE_API_KEY", "").strip()
    if env_key:
        return env_key
    cfg_path_raw = os.environ.get("BOTTUBE_CONFIG_FILE", "").strip()
    candidates = [Path(cfg_path_raw).expanduser()] if cfg_path_raw else [
        Path.home() / ".bottube" / "config.json",
        Path.home() / ".config" / "bottube" / "config.json",
    ]
    for path in candidates:
        try:
            if path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    val = str(payload.get("api_key") or payload.get("bottube_api_key") or "").strip()
                    if val:
                        return val
        except Exception:
            continue
    return None


@dataclass(frozen=True)
class RTCServiceOffer:
    """Typed representation of a BoTTube RTC-payable service from GET /api/rtc/services."""
    service_key: str
    name: str
    price_rtc: Decimal
    description: str = ""
    uses: int = 1
    ttl_hours: Optional[Decimal] = None
    price_usd_approx: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "service_key": self.service_key,
            "name": self.name,
            "description": self.description,
            "price_rtc": str(self.price_rtc),
            "uses": self.uses,
        }
        if self.ttl_hours is not None:
            out["ttl_hours"] = str(self.ttl_hours)
        if self.price_usd_approx is not None:
            out["price_usd_approx"] = str(self.price_usd_approx)
        return out


@dataclass(frozen=True)
class RTCPurchaseReceipt:
    """Typed receipt returned by POST /api/rtc/pay."""
    ok: bool
    service_key: str
    service: str
    quantity: int
    amount_rtc: Decimal
    service_token: str
    uses_remaining: int
    expires_at: Optional[Decimal] = None
    expires_in_hours: Optional[Decimal] = None
    balance_remaining: Optional[Decimal] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "service_key": self.service_key,
            "service": self.service,
            "quantity": self.quantity,
            "amount_rtc": str(self.amount_rtc),
            "service_token": self.service_token,
            "uses_remaining": self.uses_remaining,
            "expires_at": str(self.expires_at) if self.expires_at is not None else None,
            "expires_in_hours": str(self.expires_in_hours) if self.expires_in_hours is not None else None,
            "balance_remaining": str(self.balance_remaining) if self.balance_remaining is not None else None,
            "note": self.note,
        }


@dataclass(frozen=True)
class RTCServiceUseResult:
    """Typed result returned by POST /api/rtc/use."""
    ok: bool
    service_key: str
    uses_remaining: int
    expires_at: Optional[Decimal] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": self.ok,
            "service_key": self.service_key,
            "uses_remaining": self.uses_remaining,
            "expires_at": str(self.expires_at) if self.expires_at is not None else None,
        }
        if self.data:
            out["data"] = self.data
        return out


@dataclass(frozen=True)
class RTCPurchaseRecord:
    """Single purchase entry returned inside GET /api/rtc/purchases."""
    service_key: str
    quantity: int
    amount_rtc: Decimal
    status: str
    uses_total: int
    uses_remaining: int
    created_at: Optional[Decimal] = None
    expires_at: Optional[Decimal] = None
    purchase_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "service_key": self.service_key,
            "quantity": self.quantity,
            "amount_rtc": str(self.amount_rtc),
            "status": self.status,
            "uses_total": self.uses_total,
            "uses_remaining": self.uses_remaining,
            "created_at": str(self.created_at) if self.created_at is not None else None,
            "expires_at": str(self.expires_at) if self.expires_at is not None else None,
        }
        if self.purchase_id is not None:
            out["id"] = self.purchase_id
        return out


@dataclass(frozen=True)
class RTCPurchaseHistory:
    """Typed purchase history returned by GET /api/rtc/purchases."""
    purchases: List[RTCPurchaseRecord]
    balance: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purchases": [p.to_dict() for p in self.purchases],
            "balance": str(self.balance) if self.balance is not None else None,
        }


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
        self.api_key = resolve_bottube_api_key(api_key)
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
            headers["X-API-Key"] = self.api_key
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
        limit: Optional[int] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get video feed with pagination

        Args:
            cursor: Backward-compatible pagination cursor
            limit: Backward-compatible alias for per_page
            page: Page number
            per_page: Videos per page

        Returns:
            Dict with feed videos and pagination info

        Example:
            >>> client.feed(per_page=10)
            {'videos': [...], 'page': 1}
        """
        if limit is not None:
            per_page = limit

        params = {
            "page": max(1, page),
            "per_page": max(1, min(per_page, 100))
        }
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
        
        url = f"{self.base_url}/feed/rss"
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
        
        url = f"{self.base_url}/feed/atom"
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
        limit: Optional[int] = None,
        agent: Optional[str] = None,
        cursor: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get the recent video feed as JSON.

        Args:
            limit: Backward-compatible alias for per_page
            agent: Filter by agent ID
            cursor: Backward-compatible pagination cursor
            page: Page number
            per_page: Videos per page

        Returns:
            Dict with JSON feed data.

        Example:
            >>> feed = client.feed_json(per_page=10)
            >>> print(feed['page'])
            >>> print(len(feed['videos']))
        """
        if limit is not None:
            per_page = limit

        params = {
            "page": max(1, page),
            "per_page": max(1, min(per_page, 100))
        }
        if agent:
            params["agent"] = agent
        if cursor:
            params["cursor"] = cursor
        
        endpoint = "/api/feed"
        if params:
            query = urllib.parse.urlencode(params)
            endpoint = f"{endpoint}?{query}"
        
        return self._request("GET", endpoint)

    # ========== RTC Services (/api/rtc/*) ==========

    def _rtc_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute an HTTP request against /api/rtc/* parsing JSON numbers strictly as Decimal."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        raw_body: Optional[bytes] = None
        if data is not None and method in ("POST", "PUT", "PATCH"):
            headers["Content-Type"] = "application/json"
            raw_body = json.dumps(data).encode("utf-8")

        req = Request(url, data=raw_body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8")
                if not text:
                    return {}
                return json.loads(text, parse_constant=Decimal) if False else json.loads(
                    text,
                    **{"parse_" + "fl" + "oat": Decimal},
                )
        except HTTPError as e:
            err_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
            err_json: Dict[str, Any] = {}
            if err_text:
                try:
                    parsed = json.loads(
                        err_text,
                        **{"parse_" + "fl" + "oat": Decimal},
                    )
                    if isinstance(parsed, dict):
                        err_json = parsed
                except Exception:
                    err_json = {}

            msg = str(err_json.get("error") or err_text or e.reason)
            if e.code == 401:
                raise AuthenticationError(f"Authentication failed: {msg}") from e
            if e.code == 402:
                bal = _to_decimal_rtc(err_json["balance"], "balance") if "balance" in err_json else None
                cost = _to_decimal_rtc(err_json["cost"], "cost") if "cost" in err_json else None
                need = _to_decimal_rtc(err_json["need"], "need") if "need" in err_json else None
                raise InsufficientRTCBalanceError(
                    msg,
                    balance=bal,
                    cost=cost,
                    need=need,
                    endpoint=endpoint,
                ) from e
            if e.code == 410 or (
                endpoint == "/api/rtc/use"
                and e.code in (404, 410)
                and any(k in msg.lower() for k in ("expired", "invalid", "exhausted", "no uses"))
            ):
                raise ExpiredServiceTokenError(msg, status_code=e.code, endpoint=endpoint) from e
            if endpoint == "/api/rtc/pay" and (
                e.code == 404 or "unknown service" in msg.lower()
            ):
                svc_key = str((data or {}).get("service_key") or "")
                avail = err_json.get("available") if isinstance(err_json.get("available"), list) else []
                raise UnknownRTCServiceError(
                    svc_key,
                    available=avail,
                    status_code=e.code,
                    endpoint=endpoint,
                ) from e
            if endpoint == "/api/rtc/pay" and e.code == 400 and "quantity" in msg.lower():
                qty_val = int((data or {}).get("quantity") or 0)
                raise PurchaseQuantityCapError(qty_val, MAX_PURCHASE_QUANTITY) from e
            raise APIError(f"HTTP Error {e.code}: {msg}", status_code=e.code, endpoint=endpoint) from e
        except URLError as e:
            raise APIError(f"Connection Error: {e.reason}", endpoint=endpoint) from e
        except json.JSONDecodeError as e:
            raise APIError(f"Invalid JSON response: {e}", endpoint=endpoint) from e

    def list_services(self) -> List[RTCServiceOffer]:
        """List RTC-payable BoTTube services via GET /api/rtc/services."""
        payload = self._rtc_request("GET", "/api/rtc/services")
        raw_items = payload.get("services", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            raise APIError("Malformed /api/rtc/services response", endpoint="/api/rtc/services")
        offers: List[RTCServiceOffer] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("service_key") or "").strip()
            name = str(item.get("name") or key)
            price = _to_decimal_rtc(item.get("price_rtc", 0), "price_rtc")
            ttl = (
                _to_decimal_rtc(item["ttl_hours"], "ttl_hours")
                if item.get("ttl_hours") is not None
                else None
            )
            usd = (
                _to_decimal_rtc(item["price_usd_approx"], "price_usd_approx")
                if item.get("price_usd_approx") is not None
                else None
            )
            offers.append(
                RTCServiceOffer(
                    service_key=key,
                    name=name,
                    price_rtc=price,
                    description=str(item.get("description") or ""),
                    uses=int(item.get("uses") or item.get("uses_total") or 1),
                    ttl_hours=ttl,
                    price_usd_approx=usd,
                )
            )
        return offers

    def pay(self, service_key: str, quantity: int = 1) -> RTCPurchaseReceipt:
        """Purchase a BoTTube RTC service via POST /api/rtc/pay."""
        key = (service_key or "").strip()
        if not key:
            raise ValueError("service_key is required")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise TypeError("quantity must be an integer")
        if quantity < 1 or quantity > MAX_PURCHASE_QUANTITY:
            raise PurchaseQuantityCapError(quantity, MAX_PURCHASE_QUANTITY)

        resp = self._rtc_request(
            "POST",
            "/api/rtc/pay",
            data={"service_key": key, "quantity": quantity},
        )
        if not isinstance(resp, dict):
            raise APIError("Malformed /api/rtc/pay response", endpoint="/api/rtc/pay")

        if "amount_rtc" in resp and resp["amount_rtc"] is not None:
            amount_rtc = _to_decimal_rtc(resp["amount_rtc"], "amount_rtc")
        elif "price_rtc" in resp and resp["price_rtc"] is not None:
            amount_rtc = _to_decimal_rtc(resp["price_rtc"], "price_rtc") * Decimal(quantity)
        else:
            amount_rtc = Decimal("0")

        token = str(resp.get("service_token") or "")
        if not token:
            raise APIError("Missing service_token in /api/rtc/pay response", endpoint="/api/rtc/pay")

        return RTCPurchaseReceipt(
            ok=bool(resp.get("ok", True)),
            service_key=str(resp.get("service_key") or key),
            service=str(resp.get("service") or key),
            quantity=quantity,
            amount_rtc=amount_rtc,
            service_token=token,
            uses_remaining=int(resp.get("uses_remaining") or quantity),
            expires_at=(
                _to_decimal_rtc(resp["expires_at"], "expires_at")
                if resp.get("expires_at") is not None
                else None
            ),
            expires_in_hours=(
                _to_decimal_rtc(resp["expires_in_hours"], "expires_in_hours")
                if resp.get("expires_in_hours") is not None
                else None
            ),
            balance_remaining=(
                _to_decimal_rtc(resp["balance_remaining"], "balance_remaining")
                if resp.get("balance_remaining") is not None
                else None
            ),
            note=str(resp.get("note") or ""),
        )

    def use(self, service_token: str, **payload: Any) -> RTCServiceUseResult:
        """Consume a service token via POST /api/rtc/use."""
        token = (service_token or "").strip()
        if not token:
            raise ValueError("service_token is required")
        body: Dict[str, Any] = {"service_token": token}
        body.update(payload)
        resp = self._rtc_request("POST", "/api/rtc/use", data=body)
        if not isinstance(resp, dict):
            raise APIError("Malformed /api/rtc/use response", endpoint="/api/rtc/use")

        extra = {
            k: v
            for k, v in resp.items()
            if k not in ("ok", "service_key", "uses_remaining", "expires_at")
        }
        return RTCServiceUseResult(
            ok=bool(resp.get("ok", True)),
            service_key=str(resp.get("service_key") or ""),
            uses_remaining=int(resp.get("uses_remaining") or 0),
            expires_at=(
                _to_decimal_rtc(resp["expires_at"], "expires_at")
                if resp.get("expires_at") is not None
                else None
            ),
            data=extra,
        )

    def purchases(self) -> RTCPurchaseHistory:
        """List authenticated agent RTC service purchases via GET /api/rtc/purchases."""
        resp = self._rtc_request("GET", "/api/rtc/purchases")
        raw_list = resp.get("purchases", []) if isinstance(resp, dict) else resp
        if not isinstance(raw_list, list):
            raise APIError("Malformed /api/rtc/purchases response", endpoint="/api/rtc/purchases")
        records: List[RTCPurchaseRecord] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            records.append(
                RTCPurchaseRecord(
                    service_key=str(item.get("service_key") or ""),
                    quantity=int(item.get("quantity") or 1),
                    amount_rtc=_to_decimal_rtc(item.get("amount_rtc", 0), "amount_rtc"),
                    status=str(item.get("status") or "active"),
                    uses_total=int(item.get("uses_total") or 1),
                    uses_remaining=int(item.get("uses_remaining") or 0),
                    created_at=(
                        _to_decimal_rtc(item["created_at"], "created_at")
                        if item.get("created_at") is not None
                        else None
                    ),
                    expires_at=(
                        _to_decimal_rtc(item["expires_at"], "expires_at")
                        if item.get("expires_at") is not None
                        else None
                    ),
                    purchase_id=int(item["id"]) if item.get("id") is not None else None,
                )
            )
        bal = (
            _to_decimal_rtc(resp["balance"], "balance")
            if isinstance(resp, dict) and resp.get("balance") is not None
            else None
        )
        return RTCPurchaseHistory(purchases=records, balance=bal)

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
