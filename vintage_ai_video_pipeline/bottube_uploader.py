#!/usr/bin/env python3
"""
BoTTube Auto-Upload Module for Vintage AI Miner Videos
========================================================

Automatically uploads generated videos to BoTTube platform via API.
"""

import json
import os
import time
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.error import URLError, HTTPError


class BoTTubeUploader:
    """
    BoTTube Platform Auto-Uploader
    
    Handles authentication, metadata preparation, and video uploads
    to the BoTTube video platform.
    """

    DEFAULT_BASE_URL = "https://bottube.ai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        verify_ssl: bool = True,
        timeout: int = 300,  # 5 minutes for large uploads
        retry_count: int = 3,
    ):
        """
        Initialize BoTTube uploader
        
        Args:
            api_key: BoTTube API key (required for uploads)
            base_url: BoTTube API base URL
            verify_ssl: Enable SSL verification
            timeout: Upload timeout in seconds
            retry_count: Number of retries on failure
        """
        self.api_key = api_key or os.getenv("BOTTUBE_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_count = retry_count
        
        import ssl
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None
        
        if not self.api_key:
            print("⚠️  Warning: No API key provided. Uploads will fail.")
            print("   Set BOTTUBE_API_KEY environment variable or pass api_key parameter.")
        else:
            print(f"✅ BoTTube Uploader initialized")
            print(f"   URL: {self.base_url}")

    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        """Get request headers"""
        headers = {
            "Accept": "application/json",
            "User-Agent": "vintage-ai-video-pipeline/1.0",
        }
        if include_auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        for attempt in range(self.retry_count):
            try:
                if files:
                    # Multipart form data for file uploads
                    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                    body = self._encode_multipart(boundary, data, files)
                    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

                    req = urllib.request.Request(
                        url,
                        data=body.encode("utf-8"),
                        headers=headers,
                        method=method
                    )
                elif data and method in ("POST", "PUT", "PATCH"):
                    headers["Content-Type"] = "application/json"
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(data).encode("utf-8"),
                        headers=headers,
                        method=method
                    )
                else:
                    req = urllib.request.Request(url, headers=headers, method=method)

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
                    raise Exception(f"Authentication failed: {error_body}")
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
                time.sleep(2.0 * (attempt + 1))

        raise Exception("Max retries exceeded")

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
            if isinstance(content, str):
                lines.append(content)
            else:
                # Binary content - encode appropriately
                lines.append(content.decode("latin-1"))

        lines.append(f"--{boundary}--")
        lines.append("")
        return "\r\n".join(lines)

    def health_check(self) -> Dict[str, Any]:
        """Check BoTTube API health"""
        try:
            return self._request("GET", "/health")
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def prepare_metadata(
        self,
        miner_data: Dict[str, Any],
        video_info: Dict[str, Any],
        epoch_info: Optional[Dict[str, Any]] = None,
        custom_title: Optional[str] = None,
        custom_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare upload metadata from miner and video data
        
        Args:
            miner_data: Miner information
            video_info: Video generation result
            epoch_info: Epoch information
            custom_title: Override title
            custom_description: Override description
            
        Returns:
            Metadata dictionary ready for upload
        """
        # Extract miner info
        miner_id = miner_data.get("miner_id", "unknown")
        short_id = miner_id[:8] if len(miner_id) >= 8 else miner_id
        device_arch = miner_data.get("device_arch", "Unknown")
        device_family = miner_data.get("device_family", "Unknown")
        hardware_type = miner_data.get("hardware_type", "Unknown")
        multiplier = miner_data.get("antiquity_multiplier", 1.0)
        
        # Extract video info
        video_path = video_info.get("video_path", "")
        duration = video_info.get("duration", 5.0)
        
        # Get epoch info
        epoch = epoch_info.get("epoch", "?") if epoch_info else "?"
        
        # Generate title per specification:
        # [Architecture] mines block #[epoch] — [reward] RTC
        if custom_title:
            title = custom_title
        else:
            # Calculate simulated reward based on multiplier
            base_reward = 0.5
            simulated_reward = round(base_reward * multiplier, 2)
            title = f"[{device_arch}] mines block #{epoch} — {simulated_reward} RTC"
        
        # Ensure title meets BoTTube requirements (10-100 chars)
        if len(title) < 10:
            title = title + " " * (10 - len(title))
        elif len(title) > 100:
            title = title[:97] + "..."
        
        # Generate description
        if custom_description:
            description = custom_description
        else:
            description = (
                f"Watch this {hardware_type} mining RustChain cryptocurrency!\n\n"
                f"🔧 Hardware Specifications:\n"
                f"  • Architecture: {device_arch}\n"
                f"  • Family: {device_family}\n"
                f"  • Antiquity Multiplier: x{multiplier}\n\n"
                f"📊 Mining Information:\n"
                f"  • Wallet: {short_id}...\n"
                f"  • Epoch: {epoch}\n"
                f"  • Generated by Vintage AI Video Pipeline\n\n"
                f"⛏️ About RustChain:\n"
                f"RustChain is a proof-of-work cryptocurrency that rewards "
                f"vintage and diverse hardware through its antiquity-based "
                f"reward system. Older hardware receives multipliers to "
                f"remain competitive in mining.\n\n"
                f"🤖 AI Video Generation:\n"
                f"This video was automatically generated by the Vintage AI "
                f"Miner Video Pipeline, which monitors RustChain attestations "
                f"and creates unique videos for each mining event.\n\n"
                f"#RustChain #Cryptocurrency #VintageComputing #AI #Mining"
            )
        
        # Generate tags per specification:
        # mining, vintage, [architecture]
        tags = [
            "mining",
            "vintage",
            device_arch,
            "RustChain",
            "cryptocurrency",
            "blockchain",
            "AI video",
            device_family,
            f"epoch {epoch}",
        ]
        
        return {
            "title": title,
            "description": description,
            "tags": tags,
            "public": True,
            "metadata": {
                "miner_id": miner_id,
                "device_arch": device_arch,
                "device_family": device_family,
                "antiquity_multiplier": multiplier,
                "epoch": epoch,
                "video_duration": duration,
                "generated_at": datetime.utcnow().isoformat(),
                "pipeline_version": "1.0.0",
            },
        }

    def upload(
        self,
        video_path: str,
        metadata: Dict[str, Any],
        thumbnail_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload video to BoTTube
        
        Args:
            video_path: Path to video file
            metadata: Upload metadata (from prepare_metadata)
            thumbnail_path: Optional thumbnail image path
            
        Returns:
            Upload result with video ID
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        print(f"⬆️  Uploading video to BoTTube...")
        print(f"   File: {video_path}")
        print(f"   Title: {metadata.get('title', 'N/A')}")
        
        # Read video file
        with open(video_path, "rb") as f:
            video_content = f.read()
        
        # Prepare files dict
        filename = os.path.basename(video_path)
        files = {
            "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
            "video": (filename, video_content, "video/mp4"),
        }
        
        # Add thumbnail if provided
        if thumbnail_path and os.path.exists(thumbnail_path):
            with open(thumbnail_path, "rb") as f:
                thumbnail_content = f.read()
            files["thumbnail"] = (
                os.path.basename(thumbnail_path),
                thumbnail_content,
                "image/jpeg",
            )
        
        # Upload
        try:
            result = self._request(
                "POST",
                "/api/upload",
                data=metadata,
                files=files,
            )
            
            video_id = result.get("video_id") or result.get("id")
            
            print(f"✅ Upload successful!")
            print(f"   Video ID: {video_id}")
            print(f"   URL: {self.base_url}/video/{video_id}")
            
            return {
                "success": True,
                "video_id": video_id,
                "url": f"{self.base_url}/video/{video_id}",
                "metadata": metadata,
                "api_response": result,
            }
            
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": metadata,
            }

    def upload_miner_video(
        self,
        miner_data: Dict[str, Any],
        video_info: Dict[str, Any],
        epoch_info: Optional[Dict[str, Any]] = None,
        thumbnail_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete upload flow for miner video
        
        Args:
            miner_data: Miner information
            video_info: Video generation result
            epoch_info: Optional epoch information
            thumbnail_path: Optional thumbnail path
            
        Returns:
            Upload result
        """
        # Prepare metadata
        metadata = self.prepare_metadata(
            miner_data=miner_data,
            video_info=video_info,
            epoch_info=epoch_info,
        )
        
        # Upload
        video_path = video_info.get("video_path")
        if not video_path:
            return {
                "success": False,
                "error": "No video path in video_info",
            }
        
        return self.upload(
            video_path=video_path,
            metadata=metadata,
            thumbnail_path=thumbnail_path,
        )

    def dry_run(
        self,
        miner_data: Dict[str, Any],
        video_info: Dict[str, Any],
        epoch_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform dry-run upload (metadata validation only)
        
        Args:
            miner_data: Miner information
            video_info: Video generation result
            epoch_info: Optional epoch information
            
        Returns:
            Validation result
        """
        print("🧪 Performing dry-run upload validation...")
        
        try:
            metadata = self.prepare_metadata(
                miner_data=miner_data,
                video_info=video_info,
                epoch_info=epoch_info,
            )
            
            # Validate metadata
            errors = []
            
            if len(metadata["title"]) < 10:
                errors.append("Title too short (min 10 chars)")
            elif len(metadata["title"]) > 100:
                errors.append("Title too long (max 100 chars)")
            
            if len(metadata["description"]) < 50:
                errors.append("Description too short (min 50 chars recommended)")
            
            if errors:
                return {
                    "valid": False,
                    "errors": errors,
                    "metadata": metadata,
                }
            
            return {
                "valid": True,
                "metadata": metadata,
                "message": "Metadata validation passed",
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    def get_upload_queue_status(self) -> Dict[str, Any]:
        """Get upload queue status (if API supports it)"""
        try:
            return self._request("GET", "/api/upload/queue")
        except Exception as e:
            return {"status": "error", "error": str(e)}


def create_uploader(
    api_key: Optional[str] = None,
    **kwargs
) -> BoTTubeUploader:
    """Create a BoTTube uploader"""
    return BoTTubeUploader(api_key=api_key, **kwargs)


if __name__ == "__main__":
    # Demo usage
    print("📤 BoTTube Uploader Demo")
    print("=" * 50)
    
    # Create uploader (will use env var if available)
    uploader = create_uploader()
    
    # Check health
    print("\n🏥 API Health Check:")
    health = uploader.health_check()
    print(f"   Status: {json.dumps(health, indent=2)}")
    
    # Sample data for dry-run
    sample_miner = {
        "miner_id": "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC",
        "device_arch": "G4",
        "device_family": "PowerPC",
        "hardware_type": "PowerPC G4 (Vintage)",
        "antiquity_multiplier": 2.5,
    }
    
    sample_video = {
        "video_path": "./demo_videos/rustchain_eafc6f14_demo.mp4",
        "duration": 5.0,
    }
    
    sample_epoch = {"epoch": 75}
    
    # Dry-run
    print("\n🧪 Dry-Run Upload:")
    result = uploader.dry_run(
        miner_data=sample_miner,
        video_info=sample_video,
        epoch_info=sample_epoch,
    )
    print(f"   Valid: {result.get('valid')}")
    if result.get("errors"):
        print(f"   Errors: {result['errors']}")
    if result.get("metadata"):
        meta = result["metadata"]
        print(f"   Title: {meta['title']}")
        print(f"   Tags: {', '.join(meta['tags'][:5])}...")
