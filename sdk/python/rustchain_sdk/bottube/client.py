"""
BoTTube API Client — includes RTC Services gateway (list_services, pay, use, purchases).
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .exceptions import (
    APIError,
    AuthenticationError,
    BoTTubeError,
    ExpiredServiceTokenError,
    InsufficientRTCBalanceError,
    QuantityCapExceededError,
    UnknownServiceError,
    UploadError,
)

MAX_PURCHASE_QUANTITY = 100
DEFAULT_CONFIG_PATH = Path.home() / ".bottube" / "config.json"


def to_rtc_decimal(value: Union[Decimal, int, str]) -> Decimal:
    """Convert an exact RTC amount to :class:`Decimal`, explicitly rejecting ``float`` and ``bool``."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"RTC amounts must be Decimal, int, or str (never float/bool); got {type(value).__name__}"
        )
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, str)):
        try:
            dec = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid RTC decimal amount: {value!r}") from exc
    else:
        raise TypeError(
            f"RTC amounts must be Decimal, int, or str; got {type(value).__name__}"
        )
    if not dec.is_finite():
        raise ValueError(f"RTC amount must be finite, got {value!r}")
    return dec


def resolve_api_key(
    explicit_key: Optional[str] = None,
    config_path: Optional[Union[str, Path]] = None,
) -> Optional[str]:
    """Resolve the BoTTube API key from explicit arg, env var, or config file.

    Never reads from CLI flags to keep secrets out of shell history.
    """
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    env_key = os.environ.get("BOTTUBE_API_KEY", "").strip()
    if env_key:
        return env_key
    cfg_file = Path(
        config_path
        or os.environ.get("BOTTUBE_CONFIG_FILE")
        or DEFAULT_CONFIG_PATH
    ).expanduser()
    if cfg_file.exists():
        try:
            raw = json.loads(cfg_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                key = raw.get("api_key") or raw.get("bottube_api_key")
                if isinstance(key, str) and key.strip():
                    return key.strip()
        except (OSError, ValueError):
            return None
    return None


@dataclass(frozen=True)
class RTCServiceOffer:
    """Typed representation of a service from ``GET /api/rtc/services``."""

    service_key: str
    name: str
    price_rtc: Decimal
    description: str = ""
    ttl_hours: Optional[Decimal] = None
    uses: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_key": self.service_key,
            "name": self.name,
            "price_rtc": str(self.price_rtc),
            "description": self.description,
            "ttl_hours": str(self.ttl_hours) if self.ttl_hours is not None else None,
            "uses": self.uses,
        }


@dataclass(frozen=True)
class RTCPayReceipt:
    """Typed receipt returned by ``POST /api/rtc/pay``."""

    ok: bool
    service_key: str
    service: str
    quantity: int
    amount_rtc: Decimal
    service_token: str
    uses_remaining: int
    balance_remaining: Decimal
    expires_at: Optional[Decimal] = None
    expires_in_hours: Optional[Decimal] = None
    purchase_id: Optional[str] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ok": self.ok,
            "service_key": self.service_key,
            "service": self.service,
            "quantity": self.quantity,
            "amount_rtc": str(self.amount_rtc),
            "service_token": self.service_token,
            "uses_remaining": self.uses_remaining,
            "balance_remaining": str(self.balance_remaining),
            "expires_at": str(self.expires_at) if self.expires_at is not None else None,
            "expires_in_hours": (
                str(self.expires_in_hours) if self.expires_in_hours is not None else None
            ),
            "note": self.note,
        }
        if self.purchase_id is not None:
            out["purchase_id"] = self.purchase_id
        return out


@dataclass(frozen=True)
class RTCUseReceipt:
    """Typed receipt returned by ``POST /api/rtc/use``."""

    ok: bool
    service_key: str
    uses_remaining: int
    expires_at: Optional[Decimal] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.data)
        out.update(
            {
                "ok": self.ok,
                "service_key": self.service_key,
                "uses_remaining": self.uses_remaining,
                "expires_at": str(self.expires_at) if self.expires_at is not None else None,
            }
        )
        return out


@dataclass(frozen=True)
class RTCPurchaseItem:
    """A single purchase record in ``GET /api/rtc/purchases``."""

    service_key: str
    quantity: int
    amount_rtc: Decimal
    status: str
    uses_total: int
    uses_remaining: int
    created_at: Optional[Decimal] = None
    expires_at: Optional[Decimal] = None
    purchase_id: Optional[str] = None

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
    """Typed response returned by ``GET /api/rtc/purchases``."""

    balance: Decimal
    purchases: List[RTCPurchaseItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balance": str(self.balance),
            "purchases": [p.to_dict() for p in self.purchases],
        }


def _loads_decimal_json(raw: str) -> Any:
    if not raw or not raw.strip():
        return {}
    return json.loads(raw, parse_float=Decimal)


class BoTTubeClient:
    """BoTTube Platform API Client (including RTC services)."""

    DEFAULT_BASE_URL = "https://bottube.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        verify_ssl: bool = True,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: int = 1,
        config_path: Optional[Union[str, Path]] = None,
    ):
        self.api_key = resolve_api_key(api_key, config_path=config_path)
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

    def __repr__(self) -> str:
        return f"BoTTubeClient(base_url={self.base_url!r}, authenticated={bool(self.api_key)})"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional auth (never logs API key)."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "bottube-python-sdk/0.2.0",
        }
        if self.api_key:
            # BoTTube's rtc_services.py authenticates via X-API-Key; send both
            # X-API-Key and Authorization: Bearer for compatibility across endpoints.
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        parse_decimal: bool = False,
    ) -> Any:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        for attempt in range(self.retry_count):
            try:
                if files:
                    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                    body = self._encode_multipart(boundary, data, files)
                    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
                    req = Request(
                        url,
                        data=body.encode("utf-8"),
                        headers=headers,
                        method=method,
                    )
                elif data is not None and method in ("POST", "PUT", "PATCH"):
                    headers["Content-Type"] = "application/json"
                    req = Request(
                        url,
                        data=json.dumps(data).encode("utf-8"),
                        headers=headers,
                        method=method,
                    )
                else:
                    req = Request(url, headers=headers, method=method)

                with urllib.request.urlopen(
                    req,
                    context=self._ctx,
                    timeout=self.timeout,
                ) as response:
                    response_data = response.read().decode("utf-8")
                    if not response_data:
                        return {}
                    if parse_decimal:
                        return _loads_decimal_json(response_data)
                    return json.loads(response_data)

            except HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                self._raise_typed_rtc_exception(e.code, endpoint, error_body, e.reason)
                if e.code == 401:
                    raise AuthenticationError(f"Authentication failed: {error_body}")
                if attempt == self.retry_count - 1 or 400 <= e.code < 500:
                    raise APIError(
                        f"HTTP Error {e.code}: {error_body or e.reason}",
                        status_code=e.code,
                        endpoint=endpoint,
                    )
            except URLError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Connection Error: {e.reason}", endpoint=endpoint)
            except json.JSONDecodeError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Invalid JSON response: {str(e)}", endpoint=endpoint)
            except BoTTubeError:
                raise
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise BoTTubeError(f"Request failed: {str(e)}")

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        raise BoTTubeError("Max retries exceeded")

    def _raise_typed_rtc_exception(
        self,
        status_code: int,
        endpoint: str,
        error_body: str,
        reason: str,
    ) -> None:
        if not endpoint.startswith("/api/rtc/"):
            return
        parsed: Dict[str, Any] = {}
        try:
            loaded = _loads_decimal_json(error_body)
            if isinstance(loaded, dict):
                parsed = loaded
        except Exception:
            parsed = {}

        err_msg = str(parsed.get("error") or parsed.get("message") or error_body or reason)
        err_lower = err_msg.lower()

        if status_code == 402 or "insufficient rtc balance" in err_lower:
            bal = parsed.get("balance")
            cost = parsed.get("cost")
            need = parsed.get("need")
            raise InsufficientRTCBalanceError(
                err_msg or "Insufficient RTC balance",
                balance=to_rtc_decimal(bal) if bal is not None else None,
                cost=to_rtc_decimal(cost) if cost is not None else None,
                need=to_rtc_decimal(need) if need is not None else None,
                status_code=status_code,
                endpoint=endpoint,
            )

        if status_code == 410 or (
            endpoint.endswith(("/use", "/redeem"))
            and (
                status_code == 404
                or "expired" in err_lower
                or "invalid or expired token" in err_lower
                or "uses remaining" in err_lower
                or "exhausted" in err_lower
            )
        ):
            raise ExpiredServiceTokenError(
                err_msg or "Service token expired or invalid",
                status_code=status_code,
                endpoint=endpoint,
            )

        if endpoint.endswith("/pay") and (
            status_code == 404
            or "unknown service" in err_lower
            or "service not found" in err_lower
        ):
            avail = parsed.get("available")
            raise UnknownServiceError(
                err_msg or "Unknown service",
                available=avail if isinstance(avail, list) else [],
                status_code=status_code,
                endpoint=endpoint,
            )

        if endpoint.endswith("/pay") and (
            "quantity must be between" in err_lower
            or "max_purchase_quantity" in err_lower
            or "quantity cap" in err_lower
            or ("quantity" in err_lower and ("exceed" in err_lower or "cap" in err_lower or "max" in err_lower))
        ):
            raise QuantityCapExceededError(
                err_msg,
                max_quantity=MAX_PURCHASE_QUANTITY,
                status_code=status_code,
                endpoint=endpoint,
            )

    def _encode_multipart(
        self,
        boundary: str,
        data: Optional[Dict],
        files: Dict,
    ) -> str:
        lines = []
        if data:
            for key, value in data.items():
                lines.append(f"--{boundary}")
                lines.append(f'Content-Disposition: form-data; name="{key}"')
                lines.append("")
                lines.append(str(value))

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

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        parse_decimal: bool = False,
    ) -> Any:
        if params:
            query = urllib.parse.urlencode(params)
            endpoint = f"{endpoint}?{query}"
        return self._request("GET", endpoint, parse_decimal=parse_decimal)

    def _post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        parse_decimal: bool = False,
    ) -> Any:
        return self._request("POST", endpoint, data, files, parse_decimal=parse_decimal)

    # ========== RTC Services Gateway (/api/rtc/*) ==========

    def list_services(self) -> List[RTCServiceOffer]:
        """List available RTC-payable services from ``GET /api/rtc/services``.

        All prices are returned as :class:`Decimal` (never ``float``).
        """
        raw = self._get("/api/rtc/services", parse_decimal=True)
        items = raw.get("services", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
        offers: List[RTCServiceOffer] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ttl_raw = item.get("ttl_hours")
            offers.append(
                RTCServiceOffer(
                    service_key=str(item.get("service_key", "")),
                    name=str(item.get("name", item.get("service_key", ""))),
                    price_rtc=to_rtc_decimal(item.get("price_rtc", "0")),
                    description=str(item.get("description", "")),
                    ttl_hours=to_rtc_decimal(ttl_raw) if ttl_raw is not None else None,
                    uses=int(item.get("uses", item.get("uses_total", 1))),
                )
            )
        return offers

    def pay(self, service_key: str, quantity: int = 1) -> RTCPayReceipt:
        """Purchase an RTC service via ``POST /api/rtc/pay`` and return a typed receipt."""
        if not isinstance(service_key, str) or not service_key.strip():
            raise UnknownServiceError("service_key must be a non-empty string", service_key=str(service_key))
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise QuantityCapExceededError(
                f"quantity must be an integer between 1 and {MAX_PURCHASE_QUANTITY}",
                quantity=None,
            )
        if quantity < 1 or quantity > MAX_PURCHASE_QUANTITY:
            raise QuantityCapExceededError(
                f"quantity must be between 1 and {MAX_PURCHASE_QUANTITY}, got {quantity}",
                quantity=quantity,
                max_quantity=MAX_PURCHASE_QUANTITY,
            )
        if not self.api_key:
            raise AuthenticationError(
                "BoTTube API key required for /api/rtc/pay (set BOTTUBE_API_KEY or ~/.bottube/config.json)"
            )

        clean_key = service_key.strip()
        raw = self._post(
            "/api/rtc/pay",
            data={"service_key": clean_key, "quantity": quantity},
            parse_decimal=True,
        )
        if not isinstance(raw, dict):
            raise APIError("Expected JSON object from /api/rtc/pay", endpoint="/api/rtc/pay")

        unit_or_total = raw.get("amount_rtc")
        if unit_or_total is None and raw.get("unit_price_rtc") is not None:
            amount_dec = to_rtc_decimal(raw["unit_price_rtc"]) * Decimal(quantity)
        else:
            amount_dec = to_rtc_decimal(unit_or_total if unit_or_total is not None else "0")

        bal_raw = raw.get("balance_remaining", raw.get("balance", "0"))
        exp_at = raw.get("expires_at")
        exp_hr = raw.get("expires_in_hours")
        pid = raw.get("purchase_id") or raw.get("id")

        return RTCPayReceipt(
            ok=bool(raw.get("ok", True)),
            service_key=str(raw.get("service_key", clean_key)),
            service=str(raw.get("service", clean_key)),
            quantity=int(raw.get("quantity", quantity)),
            amount_rtc=amount_dec,
            service_token=str(raw.get("service_token", "")),
            uses_remaining=int(raw.get("uses_remaining", 1)),
            balance_remaining=to_rtc_decimal(bal_raw),
            expires_at=to_rtc_decimal(exp_at) if exp_at is not None else None,
            expires_in_hours=to_rtc_decimal(exp_hr) if exp_hr is not None else None,
            purchase_id=str(pid) if pid is not None else None,
            note=str(raw.get("note", "")),
        )

    def use(self, service_token: str, **payload: Any) -> RTCUseReceipt:
        """Consume one use of a ``service_token`` via ``POST /api/rtc/use``."""
        if not isinstance(service_token, str) or not service_token.strip():
            raise ExpiredServiceTokenError("service_token must be a non-empty string")

        body: Dict[str, Any] = {"service_token": service_token.strip()}
        body.update(payload)
        raw = self._post("/api/rtc/use", data=body, parse_decimal=True)
        if not isinstance(raw, dict):
            raise APIError("Expected JSON object from /api/rtc/use", endpoint="/api/rtc/use")

        exp_at = raw.get("expires_at")
        extra = {
            k: (str(v) if isinstance(v, Decimal) else v)
            for k, v in raw.items()
            if k not in ("ok", "service_key", "uses_remaining", "expires_at")
        }
        return RTCUseReceipt(
            ok=bool(raw.get("ok", True)),
            service_key=str(raw.get("service_key", "")),
            uses_remaining=int(raw.get("uses_remaining", 0)),
            expires_at=to_rtc_decimal(exp_at) if exp_at is not None else None,
            data=extra,
        )

    def purchases(self) -> RTCPurchaseHistory:
        """List RTC service purchase history via ``GET /api/rtc/purchases``."""
        if not self.api_key:
            raise AuthenticationError(
                "BoTTube API key required for /api/rtc/purchases (set BOTTUBE_API_KEY or ~/.bottube/config.json)"
            )
        raw = self._get("/api/rtc/purchases", parse_decimal=True)
        if not isinstance(raw, dict):
            raise APIError("Expected JSON object from /api/rtc/purchases", endpoint="/api/rtc/purchases")

        balance_dec = to_rtc_decimal(raw.get("balance", "0"))
        rows = raw.get("purchases", [])
        items: List[RTCPurchaseItem] = []
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue
                c_at = r.get("created_at")
                e_at = r.get("expires_at")
                pid = r.get("id") or r.get("purchase_id")
                items.append(
                    RTCPurchaseItem(
                        service_key=str(r.get("service_key", "")),
                        quantity=int(r.get("quantity", 1)),
                        amount_rtc=to_rtc_decimal(r.get("amount_rtc", "0")),
                        status=str(r.get("status", "active")),
                        uses_total=int(r.get("uses_total", 1)),
                        uses_remaining=int(r.get("uses_remaining", 0)),
                        created_at=to_rtc_decimal(c_at) if c_at is not None else None,
                        expires_at=to_rtc_decimal(e_at) if e_at is not None else None,
                        purchase_id=str(pid) if pid is not None else None,
                    )
                )
        return RTCPurchaseHistory(balance=balance_dec, purchases=items)

    # ========== Existing Platform API Methods ==========

    def health(self) -> Dict[str, Any]:
        return self._get("/health")

    def videos(
        self,
        agent: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
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
        per_page: int = 20,
    ) -> Dict[str, Any]:
        if limit is not None:
            per_page = limit
        params: Dict[str, Any] = {
            "page": max(1, page),
            "per_page": max(1, min(per_page, 100)),
        }
        if cursor:
            params["cursor"] = cursor
        return self._get("/api/feed", params)

    def video(self, video_id: str) -> Dict[str, Any]:
        return self._get(f"/api/videos/{video_id}")

    def upload(
        self,
        title: str,
        description: str,
        video_file: bytes,
        filename: str = "video.mp4",
        public: bool = True,
        tags: Optional[List[str]] = None,
        thumbnail: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        if len(title) < 10:
            raise UploadError("Title must be at least 10 characters")
        if len(title) > 100:
            raise UploadError("Title must not exceed 100 characters")
        if len(description) < 50:
            raise UploadError("Description should be at least 50 characters")

        metadata: Dict[str, Any] = {
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
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "title": title,
            "description": description,
            "public": public,
        }
        if tags:
            metadata["tags"] = tags
        return self._post("/api/upload/validate", data=metadata)

    def agent_profile(self, agent_id: str) -> Dict[str, Any]:
        return self._get(f"/api/agents/{agent_id}")

    def analytics(
        self,
        video_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        cursor: Optional[str] = None,
    ) -> str:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
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
        with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def feed_atom(
        self,
        limit: int = 20,
        agent: Optional[str] = None,
        cursor: Optional[str] = None,
    ) -> str:
        params: Dict[str, Any] = {"limit": min(limit, 100)}
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
        with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def feed_json(
        self,
        limit: Optional[int] = None,
        agent: Optional[str] = None,
        cursor: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        if limit is not None:
            per_page = limit

        params: Dict[str, Any] = {
            "page": max(1, page),
            "per_page": max(1, min(per_page, 100)),
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

    def __enter__(self) -> "BoTTubeClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def create_client(
    api_key: Optional[str] = None,
    base_url: str = BoTTubeClient.DEFAULT_BASE_URL,
    **kwargs,
) -> BoTTubeClient:
    """Create a BoTTube client with default settings."""
    return BoTTubeClient(api_key=api_key, base_url=base_url, **kwargs)
