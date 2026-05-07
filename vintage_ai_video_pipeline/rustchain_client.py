#!/usr/bin/env python3
"""
RustChain API Client for Vintage AI Video Pipeline
===================================================

Monitors miner attestations and fetches miner metadata for video generation.
"""

import json
import ssl
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List
from urllib.error import URLError, HTTPError
from urllib.request import Request
import time


class RustChainClient:
    """
    RustChain API Client
    
    Monitors miner attestations and fetches metadata for video generation.
    """

    DEFAULT_BASE_URL = "https://rustchain.org"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        verify_ssl: bool = True,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize RustChain Client

        Args:
            base_url: Base URL of the RustChain API
            verify_ssl: Enable SSL verification (default: True)
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Delay between retries (seconds)
        """
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

        self._last_attestation_check = 0
        self._known_miners = {}

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "Accept": "application/json",
            "User-Agent": "vintage-ai-video-pipeline/1.0.0",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        for attempt in range(self.retry_count):
            try:
                if data and method in ("POST", "PUT", "PATCH"):
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
                if attempt == self.retry_count - 1:
                    raise Exception(
                        f"HTTP Error {e.code}: {e.reason} - {error_body}"
                    )
            except URLError as e:
                if attempt == self.retry_count - 1:
                    raise Exception(f"Connection Error: {e.reason}")
            except json.JSONDecodeError as e:
                if attempt == self.retry_count - 1:
                    raise Exception(f"Invalid JSON response: {str(e)}")
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        raise Exception("Max retries exceeded")

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET request with query parameters"""
        if params:
            query = urllib.parse.urlencode(params)
            endpoint = f"{endpoint}?{query}"
        return self._request("GET", endpoint)

    def health(self) -> Dict[str, Any]:
        """Check node health"""
        return self._get("/health")

    def get_epoch(self) -> Dict[str, Any]:
        """Get current epoch information"""
        return self._get("/epoch")

    def get_miners(self) -> List[Dict[str, Any]]:
        """
        List all active miners
        
        Returns:
            List of miner information dictionaries
        """
        return self._get("/api/miners")

    def get_miner_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Check miner's epoch eligibility"""
        return self._get("/lottery/eligibility", params={"miner_id": miner_id})

    def get_wallet_balance(self, miner_id: str) -> Dict[str, Any]:
        """Get wallet balance for a miner"""
        return self._get("/wallet/balance", params={"miner_id": miner_id})

    def get_wallet_history(self, miner_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get transaction history for a miner"""
        return self._get("/wallet/history", params={"miner_id": miner_id, "limit": limit})

    def get_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        return self._get("/api/stats")

    def get_hall_of_fame(self) -> Dict[str, Any]:
        """Get Hall of Fame leaderboard"""
        return self._get("/api/hall_of_fame")

    def monitor_attestations(
        self,
        callback=None,
        poll_interval: int = 60,
        max_iterations: Optional[int] = None
    ):
        """
        Monitor miner attestations continuously
        
        Args:
            callback: Function to call when new attestation detected
            poll_interval: Polling interval in seconds
            max_iterations: Maximum number of polling iterations (None for infinite)
        """
        iteration = 0
        print(f"🔍 Starting attestation monitoring (interval: {poll_interval}s)")
        
        try:
            while max_iterations is None or iteration < max_iterations:
                current_miners = self.get_miners()
                current_miner_ids = {m.get("miner") for m in current_miners}
                
                # Check for new miners
                new_miners = current_miner_ids - set(self._known_miners.keys())
                
                if new_miners and callback:
                    for miner_id in new_miners:
                        miner_data = next(
                            (m for m in current_miners if m.get("miner") == miner_id),
                            None
                        )
                        if miner_data:
                            callback(miner_data, event_type="new_miner")
                
                # Check for updated attestations (last_attest timestamp changed)
                for miner in current_miners:
                    miner_id = miner.get("miner")
                    last_attest = miner.get("last_attest", 0)
                    
                    if miner_id in self._known_miners:
                        old_attest = self._known_miners[miner_id].get("last_attest", 0)
                        if last_attest > old_attest and callback:
                            callback(miner_data, event_type="attestation_updated")
                    
                    self._known_miners[miner_id] = miner
                
                self._last_attestation_check = int(time.time())
                iteration += 1
                
                if max_iterations is None or iteration < max_iterations:
                    time.sleep(poll_interval)
                    
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            raise

    def get_new_attestations_since(self, timestamp: int) -> List[Dict[str, Any]]:
        """
        Get miners who attested since a given timestamp
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            List of miner data dictionaries
        """
        miners = self.get_miners()
        return [
            m for m in miners
            if m.get("last_attest", 0) >= timestamp
        ]

    def format_miner_for_video(self, miner_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format miner data for video generation
        
        Args:
            miner_data: Raw miner data from API
            
        Returns:
            Formatted metadata for video generation
        """
        miner_id = miner_data.get("miner", "")
        short_id = miner_id[:8] if len(miner_id) >= 8 else miner_id
        
        return {
            "miner_id": miner_id,
            "short_id": short_id,
            "device_arch": miner_data.get("device_arch", "Unknown"),
            "device_family": miner_data.get("device_family", "Unknown"),
            "hardware_type": miner_data.get("hardware_type", "Unknown"),
            "antiquity_multiplier": miner_data.get("antiquity_multiplier", 1.0),
            "entropy_score": miner_data.get("entropy_score", 0.0),
            "last_attest": miner_data.get("last_attest", 0),
            "first_attest": miner_data.get("first_attest", 0),
            "visual_style": self._get_visual_style_for_arch(
                miner_data.get("device_arch", "")
            ),
        }

    def _get_visual_style_for_arch(self, device_arch: str) -> str:
        """Map device architecture to visual style for video generation
        
        Handles both uppercase (G3, G4, G5, POWER7, POWER8) and lowercase
        (power8, aarch64, apple_silicon, ivy_bridge, broadwell) formats.
        """
        # Normalize to uppercase for comparison
        arch_upper = device_arch.upper()
        arch_lower = device_arch.lower()
        
        # Vintage Apple PowerPC (G3, G4, G5)
        if arch_upper in ("G3", "G4", "G5") or arch_lower in ("powerpc", "powerpc64"):
            if arch_upper == "G3":
                return "retro_apple_performera_style"
            elif arch_upper == "G4":
                return "vintage_apple_beige_aesthetic"
            elif arch_upper == "G5":
                return "powermac_g5_aluminum_cool"
            else:
                return "vintage_apple_beige_aesthetic"  # Default for PowerPC
        
        # IBM POWER servers (POWER7, POWER8, POWER9, etc.)
        if arch_lower.startswith("power") or arch_upper.startswith("POWER"):
            if "power8" in arch_lower or "POWER8" in arch_upper:
                return "ibm_power8_datacenter"
            elif "power7" in arch_lower or "POWER7" in arch_upper:
                return "ibm_power7_server_industrial"
            else:
                return "ibm_power7_server_industrial"  # Default for POWER
        
        # Modern x86_64 variants (Ivy Bridge, Broadwell, etc.)
        x86_variants = ["ivy_bridge", "broadwell", "skylake", "haswell", "x86_64", "intel64"]
        if any(v in arch_lower for v in x86_variants) or arch_lower == "modern":
            if "windows" in device_arch.lower():
                return "modern_server_rack"
            return "modern_server_rack"
        
        # ARM/Apple Silicon
        if arch_lower in ("aarch64", "arm64", "apple_silicon", "arm"):
            return "modern_arm_cluster"
        
        # Fallback to generic vintage
        return "vintage_computer_generic"


def create_client(
    base_url: str = RustChainClient.DEFAULT_BASE_URL,
    **kwargs
) -> RustChainClient:
    """Create a RustChain client with default settings"""
    return RustChainClient(base_url=base_url, **kwargs)


if __name__ == "__main__":
    # Demo usage
    client = create_client()
    
    print("🔗 RustChain Client Demo")
    print("=" * 50)
    
    try:
        health = client.health()
        print(f"✅ Node Health: {json.dumps(health, indent=2)}")
        
        epoch = client.get_epoch()
        print(f"📊 Current Epoch: {json.dumps(epoch, indent=2)}")
        
        miners = client.get_miners()
        print(f"👥 Active Miners: {len(miners)}")
        
        if miners:
            print("\n📋 Sample Miner Data:")
            for miner in miners[:3]:
                formatted = client.format_miner_for_video(miner)
                print(f"  - {formatted['short_id']}... | {formatted['hardware_type']} | x{formatted['antiquity_multiplier']}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
