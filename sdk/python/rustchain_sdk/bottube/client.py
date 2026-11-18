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

from .exceptions import (
    BoTTubeError,
    AuthenticationError,
    APIError,
    UploadError,
    InsufficientRTCBalanceError,
    ExpiredServiceTokenError,
    UnknownServiceError,
    QuantityCapExceededError,
)


# ========== RTC Services Data Models & Endpoints (#17183) ==========

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import os as _os


def _to_decimal_rtc(val: Any, field_name: str = "amount_rtc") -> Decimal:
    """Convert raw numeric/string RTC amount to exact Decimal without float precision loss."""
    if isinstance(val, Decimal):
        d = val
    elif isinstance(val, int) and not isinstance(val, bool):
        d = Decimal(val)
    elif isinstance(val, str):
        d = Decimal(val.strip())
    elif val is not None:
        # Convert via str() so JSON-decoded numbers become exact decimal strings
        d = Decimal(str(val))
    else:
        raise ValueError(f"Missing required RTC amount field: {field_name}")
    if not d.is_finite():
        raise ValueError(f"Non-finite RTC amount for {field_name}: {val!r}")
    return d


@dataclass(frozen=True)
class RTCService:
    """Typed representation of a BoTTube RTC-payable service (`GET /api/rtc/services`)."""
    service_key: str
    name: str
    description: str
    price_rtc: Decimal
    ttl_hours: Decimal
    uses: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RTCService":
        return cls(
            service_key=str(data.get("service_key", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            price_rtc=_to_decimal_rtc(data.get("price_rtc", "0"), "price_rtc"),
            ttl_hours=_to_decimal_rtc(data.get("ttl_hours", "0"), "ttl_hours"),
            uses=int(data.get("uses", 1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_key": self.service_key,
            "name": self.name,
            "description": self.description,
            "price_rtc": str(self.price_rtc),
            "ttl_hours": str(self.ttl_hours),
            "uses": self.uses,
        }


@dataclass(frozen=True)
class RTCPaymentReceipt:
    """Typed receipt returned by `POST /api/rtc/pay`."""
    service_key: str
    service_token: str
    quantity: int
    amount_rtc: Decimal
    uses_remaining: int
    expires_at: Optional[str] = None
    purchase_id: Optional[str] = None
    balance_remaining_rtc: Optional[Decimal] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RTCPaymentReceipt":
        bal_raw = data.get("balance_remaining_rtc", data.get("new_balance_rtc"))
        return cls(
            service_key=str(data.get("service_key", "")),
            service_token=str(data.get("service_token", data.get("token", ""))),
            quantity=int(data.get("quantity", 1)),
            amount_rtc=_to_decimal_rtc(
                data.get("amount_rtc", data.get("charged_rtc", data.get("total_rtc", "0"))),
                "amount_rtc",
            ),
            uses_remaining=int(data.get("uses_remaining", data.get("uses", 1))),
            expires_at=str(data["expires_at"]) if data.get("expires_at") is not None else None,
            purchase_id=str(data.get("purchase_id", data.get("id", ""))) or None,
            balance_remaining_rtc=_to_decimal_rtc(bal_raw, "balance_remaining_rtc") if bal_raw is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "service_key": self.service_key,
            "service_token": self.service_token,
            "quantity": self.quantity,
            "amount_rtc": str(self.amount_rtc),
            "uses_remaining": self.uses_remaining,
            "expires_at": self.expires_at,
            "purchase_id": self.purchase_id,
        }
        if self.balance_remaining_rtc is not None:
            out["balance_remaining_rtc"] = str(self.balance_remaining_rtc)
        return out


@dataclass(frozen=True)
class RTCServiceUseResult:
    """Typed response returned by `POST /api/rtc/use`."""
    ok: bool
    service_key: str
    uses_remaining: int
    result: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RTCServiceUseResult":
        res_payload = data.get("result")
        if not isinstance(res_payload, dict):
            res_payload = {
                k: v for k, v in data.items()
                if k not in ("ok", "service_key", "uses_remaining")
            }
        return cls(
            ok=bool(data.get("ok", True)),
            service_key=str(data.get("service_key", "")),
            uses_remaining=int(data.get("uses_remaining", 0)),
            result=res_payload,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "service_key": self.service_key,
            "uses_remaining": self.uses_remaining,
            "result": self.result,
        }


@dataclass(frozen=True)
class RTCPurchaseRecord:
    """Typed purchase history entry returned by `GET /api/rtc/purchases`."""
    service_key: str
    quantity: int
    amount_rtc: Decimal
    status: str
    uses_total: int
    uses_remaining: int
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    purchase_id: Optional[str] = None
    token_hash: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RTCPurchaseRecord":
        return cls(
            service_key=str(data.get("service_key", "")),
            quantity=int(data.get("quantity", 1)),
            amount_rtc=_to_decimal_rtc(data.get("amount_rtc", data.get("price_rtc", "0")), "amount_rtc"),
            status=str(data.get("status", "active")),
            uses_total=int(data.get("uses_total", data.get("uses", 1))),
            uses_remaining=int(data.get("uses_remaining", 0)),
            created_at=str(data["created_at"]) if data.get("created_at") is not None else None,
            expires_at=str(data["expires_at"]) if data.get("expires_at") is not None else None,
            purchase_id=str(data.get("purchase_id", data.get("id", ""))) or None,
            token_hash=str(data["token_hash"]) if data.get("token_hash") is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "purchase_id": self.purchase_id,
            "service_key": self.service_key,
            "quantity": self.quantity,
            "amount_rtc": str(self.amount_rtc),
            "status": self.status,
            "uses_total": self.uses_total,
            "uses_remaining": self.uses_remaining,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "token_hash": self.token_hash,
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
        self.api_key = api_key or self._load_api_key_from_env_or_config()
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


    @staticmethod
    def _load_api_key_from_env_or_config() -> Optional[str]:
        """Read BoTTube API key from BOTTUBE_API_KEY / RUSTCHAIN_BOTTUBE_API_KEY env or ~/.config/rustchain/config.json."""
        for env_name in ("BOTTUBE_API_KEY", "RUSTCHAIN_BOTTUBE_API_KEY"):
            val = _os.environ.get(env_name, "").strip()
            if val:
                return val
        cfg_path = _os.path.expanduser(
            _os.environ.get("RUSTCHAIN_CONFIG_PATH", "~/.config/rustchain/config.json")
        )
        try:
            if _os.path.isfile(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                key = (cfg.get("bottube_api_key") or (cfg.get("bottube") or {}).get("api_key") or "").strip()
                if key:
                    return key
        except Exception:
            pass
        return None

    def _rtc_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        service_key: Optional[str] = None,
        quantity: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute an `/api/rtc/*` HTTP request and map HTTP error codes to typed RTC exceptions."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        req_data = None
        if data is not None and method in ("POST", "PUT", "PATCH"):
            headers["Content-Type"] = "application/json"
            req_data = json.dumps(data).encode("utf-8")

        req = Request(url, data=req_data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw, parse_float=Decimal) if raw else {}
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            parsed_err: Dict[str, Any] = {}
            try:
                parsed_err = json.loads(err_body, parse_float=Decimal) if err_body else {}
            except Exception:
                parsed_err = {}
            msg = str(parsed_err.get("error") or parsed_err.get("message") or err_body or e.reason)
            msg_lower = msg.lower()

            if e.code == 401:
                raise AuthenticationError(f"Authentication failed: {msg}")
            if e.code == 402 or "insufficient" in msg_lower:
                req_rtc = _to_decimal_rtc(parsed_err["required_rtc"], "required_rtc") if "required_rtc" in parsed_err else None
                avail_rtc = _to_decimal_rtc(parsed_err["available_rtc"], "available_rtc") if "available_rtc" in parsed_err else None
                raise InsufficientRTCBalanceError(
                    msg,
                    required_rtc=req_rtc,
                    available_rtc=avail_rtc,
                    endpoint=endpoint,
                )
            if e.code in (403, 410) or ("expired" in msg_lower or "exhausted" in msg_lower or "invalid service_token" in msg_lower or "remaining uses" in msg_lower):
                if endpoint == "/api/rtc/use":
                    raise ExpiredServiceTokenError(msg, status_code=e.code, endpoint=endpoint)
            if e.code == 404 or "unknown service" in msg_lower or "unknown service_key" in msg_lower:
                raise UnknownServiceError(
                    service_key=service_key or str(parsed_err.get("service_key", "unknown")),
                    message=msg,
                    status_code=e.code,
                    endpoint=endpoint,
                )
            if e.code in (400, 422) and ("quantity" in msg_lower or "cap" in msg_lower or "max" in msg_lower):
                max_q = int(parsed_err["max_quantity"]) if "max_quantity" in parsed_err else None
                raise QuantityCapExceededError(
                    quantity=quantity if quantity is not None else 0,
                    max_quantity=max_q,
                    message=msg,
                    status_code=e.code,
                    endpoint=endpoint,
                )
            raise APIError(f"HTTP Error {e.code}: {msg}", status_code=e.code, endpoint=endpoint)
        except URLError as e:
            raise APIError(f"Connection Error: {e.reason}", endpoint=endpoint)

    def list_services(self) -> List[RTCService]:
        """
        List RTC-payable services available on BoTTube (`GET /api/rtc/services`).

        Returns:
            List of typed `RTCService` objects with `Decimal` RTC prices.
        """
        payload = self._rtc_request("GET", "/api/rtc/services")
        raw_list = payload.get("services", []) if isinstance(payload, dict) else []
        return [RTCService.from_dict(item) for item in raw_list if isinstance(item, dict)]

    def pay(self, service_key: str, quantity: int = 1) -> RTCPaymentReceipt:
        """
        Purchase a BoTTube service with RTC (`POST /api/rtc/pay`).

        Args:
            service_key: Identifier of the service (e.g. 'inference_single')
            quantity: Number of units to purchase (1 <= quantity <= 100)

        Returns:
            Typed `RTCPaymentReceipt` containing `service_token` and `Decimal` `amount_rtc`.
        """
        if not service_key or not isinstance(service_key, str) or not service_key.strip():
            raise UnknownServiceError(str(service_key), message="service_key must be a non-empty string")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise QuantityCapExceededError(quantity=quantity, max_quantity=100, message="quantity must be a positive integer >= 1")
        if quantity > 100:
            raise QuantityCapExceededError(quantity=quantity, max_quantity=100)

        payload = self._rtc_request(
            "POST",
            "/api/rtc/pay",
            data={"service_key": service_key.strip(), "quantity": quantity},
            service_key=service_key.strip(),
            quantity=quantity,
        )
        return RTCPaymentReceipt.from_dict(payload)

    def use(self, service_token: str, **payload: Any) -> RTCServiceUseResult:
        """
        Redeem a purchased `service_token` against `POST /api/rtc/use`.

        Args:
            service_token: Token returned by `pay()`
            **payload: Service-specific parameters (e.g., `prompt="..."`)

        Returns:
            Typed `RTCServiceUseResult`.
        """
        if not service_token or not isinstance(service_token, str) or not service_token.strip():
            raise ExpiredServiceTokenError("service_token must be a non-empty string", status_code=400)
        body: Dict[str, Any] = {"service_token": service_token.strip()}
        body.update(payload)
        resp = self._rtc_request("POST", "/api/rtc/use", data=body)
        return RTCServiceUseResult.from_dict(resp)

    def purchases(self) -> List[RTCPurchaseRecord]:
        """
        List RTC service purchases for the authenticated account (`GET /api/rtc/purchases`).

        Returns:
            List of typed `RTCPurchaseRecord` objects with `Decimal` amounts.
        """
        payload = self._rtc_request("GET", "/api/rtc/purchases")
        raw_list = payload.get("purchases", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])
        return [RTCPurchaseRecord.from_dict(item) for item in raw_list if isinstance(item, dict)]

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
