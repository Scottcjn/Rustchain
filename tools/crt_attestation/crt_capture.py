"""
CRT Capture Module - Webcam and photodiode capture for CRT attestation.

Supports two capture methods:
1. USB Webcam via OpenCV - captures full frames for visual analysis
2. Photodiode + ADC via GPIO (Raspberry Pi) - precise timing capture

Both methods record the exact timing of frame changes to detect
CRT-specific characteristics like refresh rate drift and phosphor decay.
"""

import numpy as np
import time
import json
from typing import Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import struct


class CaptureMethod(Enum):
    """Supported capture methods."""
    WEBCAM = "webcam"
    PHOTODIODE = "photodiode"
    SIMULATED = "simulated"


@dataclass
class CaptureConfig:
    """Configuration for CRT capture."""
    method: str = "webcam"
    fps: int = 120  # High FPS for timing precision
    resolution: Tuple[int, int] = (640, 480)
    photodiode_pin: int = 18  # GPIO pin for photodiode
    sample_rate: int = 44100  # ADC sample rate for photodiode
    duration: float = 2.0  # Capture duration in seconds
    pattern_frequency: float = 60.0  # Expected refresh rate
    threshold: int = 128  # Brightness threshold for edge detection


@dataclass
class CaptureResult:
    """Result from a CRT capture session."""
    method: str
    timestamp: float
    duration: float
    num_frames: int
    frame_timestamps: List[float]
    brightness_values: List[float]  # Average brightness per frame
    peak_brightness: float
    frame_deltas: List[float]  # Time between consecutive frames
    capture_metadata: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "method": self.method,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "num_frames": self.num_frames,
            "frame_timestamps": self.frame_timestamps,
            "brightness_values": self.brightness_values,
            "peak_brightness": self.peak_brightness,
            "frame_deltas": self.frame_deltas,
            "capture_metadata": self.capture_metadata,
        }


class CRTCapture:
    """
    CRT capture interface for both webcam and photodiode methods.
    
    Usage:
        # Webcam capture
        capture = CRTCapture(method="webcam")
        result = capture.capture(duration=2.0)
        
        # Photodiode capture (Raspberry Pi)
        capture = CRTCapture(method="photodiode", photodiode_pin=18)
        result = capture.capture(duration=2.0)
    """
    
    def __init__(self, config: Optional[CaptureConfig] = None, **kwargs):
        """
        Initialize CRT capture.
        
        Args:
            config: CaptureConfig object, or kwargs to create one
            **kwargs: Override config fields
        """
        if config is None:
            config = CaptureConfig(**kwargs)
        elif kwargs:
            # Override specific fields
            config_dict = asdict(config)
            config_dict.update(kwargs)
            config = CaptureConfig(**config_dict)
            
        self.config = config
        self.method = CaptureMethod(config.method)
        self._cv2 = None  # Lazy load OpenCV
        self._gpio = None  # Lazy load GPIO
        self._photodiode_adc = None  # Lazy load ADC
        self._webcam = None
        self._capture_start_time = None
        
    def _ensure_opencv(self):
        """Lazily import and initialize OpenCV."""
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
            except ImportError:
                raise ImportError(
                    "OpenCV (cv2) not installed. Install with: pip install opencv-python"
                )
    
    def _ensure_gpio(self):
        """Lazily import and initialize GPIO."""
        if self._gpio is None:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.config.photodiode_pin, GPIO.IN)
                self._gpio = GPIO
            except ImportError:
                raise ImportError(
                    "RPi.GPIO not installed. This method requires Raspberry Pi."
                )
    
    def _ensure_adc(self):
        """Lazily initialize ADC for photodiode."""
        if self._photodiode_adc is None:
            try:
                import Adafruit_ADS1x15
                self._adc = Adafruit_ADS1x15.ADS1115()
            except ImportError:
                # Fall back to mock ADC
                self._adc = MockADC()
    
    def _get_webcam(self):
        """Get or initialize webcam capture."""
        self._ensure_opencv()
        
        if self._webcam is None:
            self._webcam = self._cv2.VideoCapture(0)
            
            # Configure camera for high FPS if possible
            self._webcam.set(
                self._cv2.CAP_PROP_FPS, 
                self.config.fps
            )
            self._webcam.set(
                self._cv2.CAP_PROP_FRAME_WIDTH, 
                self.config.resolution[0]
            )
            self._webcam.set(
                self._cv2.CAP_PROP_FRAME_HEIGHT, 
                self.config.resolution[1]
            )
            
            if not self._webcam.isOpened():
                raise RuntimeError("Failed to open webcam")
                
        return self._webcam
    
    def _calculate_brightness(self, frame) -> float:
        """Calculate average brightness of a frame."""
        # Convert to grayscale
        if len(frame.shape) == 3:
            gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        return float(np.mean(gray))
    
    def capture_webcam(self, duration: Optional[float] = None) -> CaptureResult:
        """
        Capture frames from webcam.
        
        Args:
            duration: Capture duration in seconds (uses config default if None)
            
        Returns:
            CaptureResult with timing and brightness data
        """
        duration = duration or self.config.duration
        self._capture_start_time = time.time()
        
        webcam = self._get_webcam()
        frames = []
        timestamps = []
        brightness_values = []
        
        start_time = time.perf_counter()
        end_time = start_time + duration
        
        print(f"Starting webcam capture for {duration}s at {self.config.fps} FPS...")
        
        frame_count = 0
        while time.perf_counter() < end_time:
            ret, frame = webcam.read()
            if not ret:
                break
                
            timestamp = time.perf_counter() - start_time
            brightness = self._calculate_brightness(frame)
            
            timestamps.append(timestamp)
            brightness_values.append(brightness)
            frames.append(frame)
            frame_count += 1
            
        actual_duration = time.perf_counter() - start_time
        
        # Calculate frame deltas
        frame_deltas = np.diff(timestamps).tolist() if len(timestamps) > 1 else []
        
        # Calculate frame rate
        actual_fps = frame_count / actual_duration if actual_duration > 0 else 0
        
        result = CaptureResult(
            method="webcam",
            timestamp=self._capture_start_time,
            duration=actual_duration,
            num_frames=frame_count,
            frame_timestamps=timestamps,
            brightness_values=brightness_values,
            peak_brightness=max(brightness_values) if brightness_values else 0,
            frame_deltas=frame_deltas,
            capture_metadata={
                "configured_fps": self.config.fps,
                "actual_fps": actual_fps,
                "resolution": self.config.resolution,
                "duration_config": duration,
            }
        )
        
        print(f"Capture complete: {frame_count} frames at {actual_fps:.1f} FPS")
        
        return result
    
    def capture_photodiode(self, duration: Optional[float] = None) -> CaptureResult:
        """
        Capture analog signal from photodiode via ADC on GPIO.
        
        This method provides more precise timing than webcam,
        suitable for detecting subtle phosphor decay curves.
        
        Args:
            duration: Capture duration in seconds
            
        Returns:
            CaptureResult with high-precision timing data
        """
        duration = duration or self.config.duration
        self._ensure_gpio()
        self._ensure_adc()
        self._capture_start_time = time.time()
        
        print(f"Starting photodiode capture for {duration}s...")
        
        samples = []
        timestamps = []
        
        start_time = time.perf_counter()
        end_time = start_time + duration
        
        # Calculate sample interval
        sample_interval = 1.0 / self.config.sample_rate
        next_sample_time = start_time
        
        while time.perf_counter() < end_time:
            current_time = time.perf_counter()
            
            if current_time >= next_sample_time:
                # Read ADC value
                try:
                    value = self._adc.read_adc(0, gain=1)  # Channel 0
                except:
                    value = int(np.random.random() * 1000)  # Mock fallback
                
                samples.append(value)
                timestamps.append(current_time - start_time)
                next_sample_time += sample_interval
                
            # Small sleep to prevent CPU spinning
            time.sleep(0.00001)
        
        actual_duration = time.perf_counter() - start_time
        num_samples = len(samples)
        actual_rate = num_samples / actual_duration if actual_duration > 0 else 0
        
        # Normalize samples to brightness-like values (0-255)
        if samples:
            max_val = max(samples)
            min_val = min(samples)
            if max_val > min_val:
                brightness_values = [
                    int((v - min_val) / (max_val - min_val) * 255) 
                    for v in samples
                ]
            else:
                brightness_values = [128] * len(samples)
        else:
            brightness_values = []
        
        # Calculate sample deltas
        sample_deltas = np.diff(timestamps).tolist() if len(timestamps) > 1 else []
        
        result = CaptureResult(
            method="photodiode",
            timestamp=self._capture_start_time,
            duration=actual_duration,
            num_frames=num_samples,
            frame_timestamps=timestamps,
            brightness_values=brightness_values,
            peak_brightness=max(brightness_values) if brightness_values else 0,
            frame_deltas=sample_deltas,
            capture_metadata={
                "sample_rate_config": self.config.sample_rate,
                "actual_sample_rate": actual_rate,
                "photodiode_pin": self.config.photodiode_pin,
                "duration_config": duration,
            }
        )
        
        print(f"Capture complete: {num_samples} samples at {actual_rate:.1f} Hz")
        
        return result
    
    def capture_simulated(self, duration: Optional[float] = None) -> CaptureResult:
        """
        Generate simulated capture data for testing without hardware.
        
        Args:
            duration: Capture duration in seconds
            
        Returns:
            CaptureResult with simulated CRT-like data
        """
        duration = duration or self.config.duration
        self._capture_start_time = time.time()
        
        print(f"Generating simulated CRT capture for {duration}s...")
        
        # Expected frame timing at configured refresh rate
        frame_period = 1.0 / self.config.pattern_frequency
        num_frames = int(duration * self.config.pattern_frequency)
        
        timestamps = []
        brightness_values = []
        
        # Simulate phosphor decay curve (P43 green phosphor)
        decay_rate = 0.15
        decay_factor = np.exp(-decay_rate * frame_period)
        
        brightness = 0
        for i in range(num_frames):
            timestamp = i * frame_period
            
            # Alternate between bright and dark frames
            if i % 2 == 0:
                brightness = 255
            else:
                brightness = int(brightness * decay_factor)
            
            # Add small deterministic noise
            noise = int((hashlib.md5(f"{i}".encode()).hexdigest()[:2], 16) % 10 - 5)
            brightness = max(0, min(255, brightness + noise))
            
            timestamps.append(timestamp)
            brightness_values.append(brightness)
        
        # Add small timing jitter (flyback transformer wear simulation)
        frame_deltas = []
        for i in range(1, len(timestamps)):
            delta = timestamps[i] - timestamps[i-1]
            # Add 0.1% typical jitter
            jitter = delta * 0.001 * (hash(i) % 100 - 50) / 50
            frame_deltas.append(delta + jitter)
        
        result = CaptureResult(
            method="simulated",
            timestamp=self._capture_start_time,
            duration=duration,
            num_frames=num_frames,
            frame_timestamps=timestamps,
            brightness_values=brightness_values,
            peak_brightness=max(brightness_values),
            frame_deltas=frame_deltas,
            capture_metadata={
                "simulated_refresh_rate": self.config.pattern_frequency,
                "phosphor_type": "P43",
                "decay_rate": decay_rate,
                "jitter_percent": 0.1,
                "note": "Simulated data for testing without CRT hardware",
            }
        )
        
        print(f"Simulated capture complete: {num_frames} frames")
        
        return result
    
    def capture(self, duration: Optional[float] = None) -> CaptureResult:
        """
        Capture CRT signal using the configured method.
        
        Args:
            duration: Capture duration in seconds
            
        Returns:
            CaptureResult with timing and brightness data
        """
        if self.method == CaptureMethod.WEBCAM:
            return self.capture_webcam(duration)
        elif self.method == CaptureMethod.PHOTODIODE:
            return self.capture_photodiode(duration)
        elif self.method == CaptureMethod.SIMULATED:
            return self.capture_simulated(duration)
        else:
            raise ValueError(f"Unknown capture method: {self.method}")
    
    def save_capture(self, result: CaptureResult, filepath: str):
        """Save capture result to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Capture saved to {filepath}")
    
    def close(self):
        """Release all capture resources."""
        if self._webcam is not None:
            self._webcam.release()
            self._webcam = None
            
        if self._gpio is not None:
            try:
                self._gpio.cleanup()
            except:
                pass
            self._gpio = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class MockADC:
    """Mock ADC for testing without hardware."""
    
    def __init__(self):
        self._t = 0
        
    def read_adc(self, channel=0, gain=1):
        """Return simulated ADC value with some variation."""
        self._t += 0.0001
        # Simulate photodiode reading with some sine wave + noise
        base = 500 + 200 * np.sin(self._t * 1000)
        noise = np.random.random() * 20 - 10
        return int(base + noise)


def create_capture(method: str = "webcam", **kwargs) -> CRTCapture:
    """
    Factory function to create a CRT capture instance.
    
    Args:
        method: 'webcam', 'photodiode', or 'simulated'
        **kwargs: Additional configuration parameters
        
    Returns:
        CRTCapture instance
    """
    return CRTCapture(config=CaptureConfig(method=method, **kwargs))


if __name__ == "__main__":
    print("CRT Capture Module - Demo")
    print("=" * 50)
    
    # Test with simulated capture
    print("\n1. Testing simulated capture...")
    capture = create_capture(method="simulated", pattern_frequency=60.0)
    result = capture.capture(duration=1.0)
    
    print(f"   Method: {result.method}")
    print(f"   Frames: {result.num_frames}")
    print(f"   Duration: {result.duration:.3f}s")
    print(f"   Peak brightness: {result.peak_brightness}")
    print(f"   Avg frame delta: {np.mean(result.frame_deltas)*1000:.3f}ms")
    
    # Save to file
    capture.save_capture(result, "capture_demo.json")
    
    print("\n2. Capture config options:")
    config = CaptureConfig()
    for field, value in asdict(config).items():
        print(f"   {field}: {value}")
    
    capture.close()
