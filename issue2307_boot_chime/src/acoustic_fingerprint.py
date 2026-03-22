"""
Acoustic Fingerprint Extraction

Extracts unique acoustic fingerprints from audio samples using spectral analysis,
MFCC (Mel-Frequency Cepstral Coefficients), and temporal features.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import json


@dataclass
class FingerprintFeatures:
    """Extracted features from audio sample"""
    mfcc_mean: np.ndarray
    mfcc_std: np.ndarray
    spectral_centroid: float
    spectral_bandwidth: float
    spectral_rolloff: float
    zero_crossing_rate: float
    chroma_mean: np.ndarray
    temporal_envelope: np.ndarray
    peak_frequencies: List[float]
    harmonic_structure: Dict[str, float]
    
    def to_vector(self) -> np.ndarray:
        """Convert features to fixed-length vector for comparison"""
        return np.concatenate([
            self.mfcc_mean,
            self.mfcc_std,
            [self.spectral_centroid],
            [self.spectral_bandwidth],
            [self.spectral_rolloff],
            [self.zero_crossing_rate],
            self.chroma_mean,
            self.temporal_envelope[:10],  # First 10 samples
            self.peak_frequencies[:5],  # Top 5 peaks
            list(self.harmonic_structure.values()),
        ])


class AcousticFingerprint:
    """
    Acoustic fingerprint extractor and matcher.
    
    Extracts unique hardware signatures from boot chime audio recordings.
    Each physical device produces subtly different acoustic characteristics
    due to manufacturing variations in speakers, amplifiers, and chassis.
    """
    
    def __init__(self, sample_rate: int = 44100, n_mfcc: int = 13):
        self.sample_rate = sample_rate
        self.n_mfcc = n_mfcc
        self.fft_size = 2048
        self.hop_size = 512
        
    def extract(self, audio_data: np.ndarray) -> FingerprintFeatures:
        """
        Extract acoustic fingerprint features from audio data.
        
        Args:
            audio_data: Raw audio samples (mono, normalized to [-1, 1])
            
        Returns:
            FingerprintFeatures object containing extracted features
        """
        # Ensure mono
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Normalize
        audio_data = self._normalize(audio_data)
        
        # Extract MFCC
        mfcc = self._extract_mfcc(audio_data)
        
        # Extract spectral features
        spectral_centroid = self._spectral_centroid(audio_data)
        spectral_bandwidth = self._spectral_bandwidth(audio_data)
        spectral_rolloff = self._spectral_rolloff(audio_data)
        
        # Extract temporal features
        zcr = self._zero_crossing_rate(audio_data)
        temporal_env = self._temporal_envelope(audio_data)
        
        # Extract chroma features
        chroma = self._extract_chroma(audio_data)
        
        # Find peak frequencies
        peak_freqs = self._find_peak_frequencies(audio_data)
        
        # Analyze harmonic structure
        harmonic = self._analyze_harmonics(audio_data)
        
        return FingerprintFeatures(
            mfcc_mean=np.mean(mfcc, axis=1),
            mfcc_std=np.std(mfcc, axis=1),
            spectral_centroid=spectral_centroid,
            spectral_bandwidth=spectral_bandwidth,
            spectral_rolloff=spectral_rolloff,
            zero_crossing_rate=zcr,
            chroma_mean=np.mean(chroma, axis=1),
            temporal_envelope=temporal_env,
            peak_frequencies=peak_freqs,
            harmonic_structure=harmonic,
        )
    
    def compute_signature(self, features: FingerprintFeatures) -> str:
        """
        Compute deterministic signature hash from features.
        
        Args:
            features: Extracted fingerprint features
            
        Returns:
            Hex string signature (SHA-256)
        """
        vector = features.to_vector()
        # Quantize to reduce noise sensitivity
        quantized = np.round(vector, decimals=4)
        data = quantized.tobytes()
        return hashlib.sha256(data).hexdigest()[:32]
    
    def compare(self, features1: FingerprintFeatures, 
                features2: FingerprintFeatures,
                threshold: float = 0.85) -> Tuple[bool, float]:
        """
        Compare two fingerprints for similarity.
        
        Args:
            features1: First fingerprint features
            features2: Second fingerprint features
            threshold: Similarity threshold (0-1)
            
        Returns:
            Tuple of (is_match, similarity_score)
        """
        vec1 = features1.to_vector()
        vec2 = features2.to_vector()
        
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)
        
        # Cosine similarity
        similarity = float(np.dot(vec1_norm, vec2_norm))
        
        # Weight MFCC features more heavily (most distinctive)
        mfcc_len = len(features1.mfcc_mean) + len(features1.mfcc_std)
        mfcc_weight = 0.5
        mfcc_sim = self._cosine_similarity(
            np.concatenate([features1.mfcc_mean, features1.mfcc_std]),
            np.concatenate([features2.mfcc_mean, features2.mfcc_std])
        )
        
        # Weighted combination
        final_similarity = mfcc_weight * mfcc_sim + (1 - mfcc_weight) * similarity
        
        return final_similarity >= threshold, final_similarity
    
    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to [-1, 1]"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            return audio / max_val
        return audio
    
    def _extract_mfcc(self, audio: np.ndarray) -> np.ndarray:
        """Extract MFCC using simplified DCT approach"""
        # Compute STFT
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        
        # Apply mel filterbank
        mel_spec = self._mel_filterbank(magnitude)
        
        # Add small epsilon to avoid log(0)
        mel_spec = np.log(mel_spec + 1e-10)
        
        # DCT to get MFCC
        mfcc = self._dct(mel_spec, n=self.n_mfcc)
        
        return mfcc
    
    def _stft(self, audio: np.ndarray) -> np.ndarray:
        """Short-Time Fourier Transform"""
        n_frames = 1 + (len(audio) - self.fft_size) // self.hop_size
        window = np.hanning(self.fft_size)
        
        frames = np.zeros((n_frames, self.fft_size))
        for i in range(n_frames):
            start = i * self.hop_size
            frames[i] = audio[start:start + self.fft_size] * window
        
        return np.fft.rfft(frames, axis=1).T
    
    def _mel_filterbank(self, magnitude: np.ndarray) -> np.ndarray:
        """Apply mel-scale filterbank"""
        n_mels = 40
        n_fft = self.fft_size
        
        # Create mel filterbank
        f_min = 0
        f_max = self.sample_rate / 2
        mel_min = self._hz_to_mel(f_min)
        mel_max = self._hz_to_mel(f_max)
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = self._mel_to_hz(mel_points)
        
        # Convert to FFT bins
        bin_points = ((n_fft + 1) * hz_points / self.sample_rate).astype(int)
        
        # Create filters
        filters = np.zeros((n_mels, n_fft // 2 + 1))
        for i in range(n_mels):
            for j in range(bin_points[i], bin_points[i + 1]):
                if j < len(filters[i]):
                    filters[i, j] = (j - bin_points[i]) / (bin_points[i + 1] - bin_points[i])
            for j in range(bin_points[i + 1], bin_points[i + 2]):
                if j < len(filters[i]):
                    filters[i, j] = (bin_points[i + 2] - j) / (bin_points[i + 2] - bin_points[i + 1])
        
        # Apply filters
        return np.dot(filters, magnitude)
    
    def _hz_to_mel(self, hz: float) -> float:
        """Convert Hz to mel scale"""
        return 2595 * np.log10(1 + hz / 700)
    
    def _mel_to_hz(self, mel: float) -> float:
        """Convert mel scale to Hz"""
        return 700 * (10 ** (mel / 2595) - 1)
    
    def _dct(self, data: np.ndarray, n: int) -> np.ndarray:
        """Discrete Cosine Transform Type II"""
        N = data.shape[0]
        n = min(n, N)
        dct_matrix = np.zeros((n, N))
        for k in range(n):
            for n_idx in range(N):
                dct_matrix[k, n_idx] = np.cos(np.pi * k * (2 * n_idx + 1) / (2 * N))
        return np.dot(dct_matrix, data)
    
    def _spectral_centroid(self, audio: np.ndarray) -> float:
        """Compute spectral centroid (center of mass of spectrum)"""
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        frequencies = np.linspace(0, self.sample_rate / 2, magnitude.shape[0])
        
        # Weighted average
        total_energy = np.sum(magnitude, axis=0) + 1e-10
        centroid = np.sum(frequencies[:, np.newaxis] * magnitude, axis=0) / total_energy
        
        return float(np.mean(centroid))
    
    def _spectral_bandwidth(self, audio: np.ndarray) -> float:
        """Compute spectral bandwidth (spread around centroid)"""
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        frequencies = np.linspace(0, self.sample_rate / 2, magnitude.shape[0])
        
        centroid = self._spectral_centroid(audio)
        
        # Variance around centroid
        variance = np.sum(((frequencies[:, np.newaxis] - centroid) ** 2) * magnitude, axis=0)
        bandwidth = np.sqrt(variance / (np.sum(magnitude, axis=0) + 1e-10))
        
        return float(np.mean(bandwidth))
    
    def _spectral_rolloff(self, audio: np.ndarray, roll_percent: float = 0.85) -> float:
        """Compute spectral rolloff (frequency below which X% of energy lies)"""
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        frequencies = np.linspace(0, self.sample_rate / 2, magnitude.shape[0])
        
        total_energy = np.sum(magnitude, axis=0) + 1e-10
        cumsum = np.cumsum(magnitude, axis=0) / total_energy
        
        rolloff_bins = np.argmax(cumsum > roll_percent * total_energy, axis=0)
        rolloff_freqs = frequencies[rolloff_bins]
        
        return float(np.mean(rolloff_freqs))
    
    def _zero_crossing_rate(self, audio: np.ndarray) -> float:
        """Compute zero crossing rate"""
        signs = np.sign(audio)
        zero_crossings = np.diff(signs != 0)
        return float(np.sum(zero_crossings) / (2 * len(audio)))
    
    def _temporal_envelope(self, audio: np.ndarray, n_bins: int = 50) -> np.ndarray:
        """Extract temporal envelope (amplitude over time)"""
        # Compute RMS in short windows
        window_size = len(audio) // n_bins
        envelope = np.zeros(n_bins)
        
        for i in range(n_bins):
            start = i * window_size
            end = start + window_size
            if end <= len(audio):
                envelope[i] = np.sqrt(np.mean(audio[start:end] ** 2))
        
        return envelope
    
    def _extract_chroma(self, audio: np.ndarray) -> np.ndarray:
        """Extract chroma features (pitch class profile)"""
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        frequencies = np.linspace(0, self.sample_rate / 2, magnitude.shape[0])
        
        # Map frequencies to pitch classes (12 semitones)
        chroma = np.zeros((12, magnitude.shape[1]))
        
        for i, freq in enumerate(frequencies):
            if freq > 0:
                # Convert to MIDI note number
                midi_note = 69 + 12 * np.log2(freq / 440)
                pitch_class = int(midi_note) % 12
                chroma[pitch_class] += magnitude[i]
        
        # Normalize
        chroma_sum = np.sum(chroma, axis=0, keepdims=True) + 1e-10
        chroma = chroma / chroma_sum
        
        return chroma
    
    def _find_peak_frequencies(self, audio: np.ndarray, n_peaks: int = 10) -> List[float]:
        """Find dominant frequencies in spectrum"""
        fft_result = np.fft.rfft(audio)
        magnitude = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(len(audio), 1 / self.sample_rate)
        
        # Find peaks
        peak_indices = self._find_peaks(magnitude, n_peaks)
        return [float(frequencies[i]) for i in peak_indices]
    
    def _find_peaks(self, data: np.ndarray, n_peaks: int) -> np.ndarray:
        """Find local maxima in 1D array"""
        # Simple peak detection
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append((i, data[i]))
        
        # Sort by magnitude and take top N
        peaks.sort(key=lambda x: x[1], reverse=True)
        return np.array([p[0] for p in peaks[:n_peaks]])
    
    def _analyze_harmonics(self, audio: np.ndarray) -> Dict[str, float]:
        """Analyze harmonic structure"""
        peak_freqs = self._find_peak_frequencies(audio, n_peaks=5)
        
        if len(peak_freqs) == 0:
            return {"fundamental": 0, "harmonicity": 0, "inharmonicity": 0}
        
        fundamental = min(peak_freqs)
        harmonics = []
        inharmonics = []
        
        for freq in peak_freqs[1:]:
            # Check if this is a harmonic (integer multiple of fundamental)
            ratio = freq / fundamental
            nearest_int = round(ratio)
            if abs(ratio - nearest_int) < 0.1:  # Within 10% of integer
                harmonics.append(freq)
            else:
                inharmonics.append(freq)
        
        total = len(harmonics) + len(inharmonics) + 1
        return {
            "fundamental": fundamental,
            "harmonicity": (len(harmonics) + 1) / total,
            "inharmonicity": len(inharmonics) / total,
        }
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
