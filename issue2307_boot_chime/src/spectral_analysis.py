"""
Spectral Analysis Utilities

Advanced spectral analysis tools for acoustic hardware attestation.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SpectralFeatures:
    """Complete spectral feature set"""
    centroid: float
    bandwidth: float
    contrast: float
    flatness: float
    rolloff: float
    slope: float
    decrease: float
    variation: float


class SpectralAnalyzer:
    """
    Advanced spectral analysis for audio signals.
    
    Provides detailed frequency domain analysis for hardware
    fingerprint extraction.
    """
    
    def __init__(self, sample_rate: int = 44100, fft_size: int = 2048):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.hop_size = fft_size // 4
        
    def analyze(self, audio: np.ndarray) -> SpectralFeatures:
        """
        Perform complete spectral analysis.
        
        Args:
            audio: Input audio signal
            
        Returns:
            SpectralFeatures object
        """
        # Compute STFT
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        frequencies = self._get_frequencies()
        
        return SpectralFeatures(
            centroid=self._compute_centroid(magnitude, frequencies),
            bandwidth=self._compute_bandwidth(magnitude, frequencies),
            contrast=self._compute_contrast(magnitude),
            flatness=self._compute_flatness(magnitude),
            rolloff=self._compute_rolloff(magnitude, frequencies),
            slope=self._compute_slope(magnitude, frequencies),
            decrease=self._compute_decrease(magnitude, frequencies),
            variation=self._compute_variation(magnitude)
        )
    
    def compute_spectrogram(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute spectrogram (time-frequency representation).
        
        Returns:
            Tuple of (spectrogram, times, frequencies)
        """
        stft = self._stft(audio)
        magnitude = np.abs(stft)
        
        n_frames = magnitude.shape[1]
        times = np.arange(n_frames) * self.hop_size / self.sample_rate
        frequencies = self._get_frequencies()
        
        return magnitude, times, frequencies
    
    def extract_formants(self, audio: np.ndarray, n_formants: int = 4) -> List[float]:
        """
        Extract formant frequencies (resonant peaks).
        
        Useful for identifying resonant characteristics of hardware.
        """
        # Use LPC (Linear Predictive Coding) for formant estimation
        lpc_coeffs = self._lpc(audio, order=14)
        
        # Find roots of LPC polynomial
        roots = np.roots(lpc_coeffs)
        
        # Keep only complex roots (conjugate pairs)
        formants = []
        for root in roots:
            if np.imag(root) > 0:
                angle = np.angle(root)
                freq = angle * self.sample_rate / (2 * np.pi)
                if 50 < freq < self.sample_rate / 2:  # Valid frequency range
                    formants.append(freq)
        
        # Sort and return top N
        formants.sort()
        return formants[:n_formants]
    
    def compute_cepstrum(self, audio: np.ndarray) -> np.ndarray:
        """
        Compute cepstrum (spectrum of spectrum).
        
        Useful for detecting periodic structure in spectrum.
        """
        # Compute FFT
        fft_data = np.fft.fft(audio)
        
        # Log magnitude
        log_magnitude = np.log(np.abs(fft_data) + 1e-10)
        
        # Inverse FFT
        cepstrum = np.fft.ifft(log_magnitude)
        
        return np.real(cepstrum)
    
    def detect_pitch(self, audio: np.ndarray) -> Optional[float]:
        """
        Detect fundamental frequency (pitch).
        
        Uses autocorrelation method.
        """
        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-10)
        
        # Compute autocorrelation
        autocorr = np.correlate(audio, audio, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        # Find first significant peak
        for i in range(int(self.sample_rate / 1000), len(autocorr)):
            if autocorr[i] > 0.3 * autocorr[0]:
                if i > 0 and autocorr[i] > autocorr[i-1] and autocorr[i] > autocorr[i+1]:
                    return self.sample_rate / i
        
        return None
    
    def _stft(self, audio: np.ndarray) -> np.ndarray:
        """Short-Time Fourier Transform"""
        n_frames = 1 + (len(audio) - self.fft_size) // self.hop_size
        window = np.hanning(self.fft_size)
        
        frames = np.zeros((n_frames, self.fft_size))
        for i in range(n_frames):
            start = i * self.hop_size
            end = min(start + self.fft_size, len(audio))
            frames[i, :end-start] = audio[start:end] * window
        
        return np.fft.rfft(frames, axis=1).T
    
    def _get_frequencies(self) -> np.ndarray:
        """Get frequency bins"""
        return np.linspace(0, self.sample_rate / 2, self.fft_size // 2 + 1)
    
    def _compute_centroid(self, magnitude: np.ndarray, 
                         frequencies: np.ndarray) -> float:
        """Spectral centroid (center of mass)"""
        total = np.sum(magnitude, axis=0) + 1e-10
        centroid = np.sum(frequencies[:, np.newaxis] * magnitude, axis=0) / total
        return float(np.mean(centroid))
    
    def _compute_bandwidth(self, magnitude: np.ndarray,
                          frequencies: np.ndarray) -> float:
        """Spectral bandwidth (spread)"""
        centroid = self._compute_centroid(magnitude, frequencies)
        total = np.sum(magnitude, axis=0) + 1e-10
        variance = np.sum(((frequencies[:, np.newaxis] - centroid) ** 2) * magnitude, axis=0)
        bandwidth = np.sqrt(variance / total)
        return float(np.mean(bandwidth))
    
    def _compute_contrast(self, magnitude: np.ndarray) -> float:
        """Spectral contrast (difference between peaks and valleys)"""
        # Simplified: difference between high and low frequency energy
        n_bins = magnitude.shape[0]
        low_energy = np.mean(magnitude[:n_bins//4])
        high_energy = np.mean(magnitude[3*n_bins//4:])
        return float(high_energy - low_energy)
    
    def _compute_flatness(self, magnitude: np.ndarray) -> float:
        """Spectral flatness (tonal vs noise-like)"""
        # Geometric mean / Arithmetic mean
        magnitude_flat = magnitude.flatten()
        magnitude_flat = magnitude_flat[magnitude_flat > 0]  # Avoid log(0)
        
        if len(magnitude_flat) == 0:
            return 0.0
        
        geometric_mean = np.exp(np.mean(np.log(magnitude_flat)))
        arithmetic_mean = np.mean(magnitude_flat)
        
        return float(geometric_mean / (arithmetic_mean + 1e-10))
    
    def _compute_rolloff(self, magnitude: np.ndarray,
                        frequencies: np.ndarray) -> float:
        """Spectral rolloff frequency"""
        total_energy = np.sum(magnitude, axis=0) + 1e-10
        cumsum = np.cumsum(magnitude, axis=0) / total_energy
        
        rolloff_threshold = 0.85
        rolloff_bins = np.argmax(cumsum > rolloff_threshold, axis=0)
        rolloff_freqs = frequencies[rolloff_bins]
        
        return float(np.mean(rolloff_freqs))
    
    def _compute_slope(self, magnitude: np.ndarray,
                      frequencies: np.ndarray) -> float:
        """Spectral slope (linear regression)"""
        # Fit line to spectrum
        magnitude_flat = magnitude.flatten()
        freq_flat = np.tile(frequencies, magnitude.shape[1])
        
        if len(magnitude_flat) < 2:
            return 0.0
        
        # Linear regression
        A = np.vstack([freq_flat, np.ones(len(freq_flat))]).T
        m, _ = np.linalg.lstsq(A, magnitude_flat, rcond=None)[0]
        
        return float(m)
    
    def _compute_decrease(self, magnitude: np.ndarray,
                         frequencies: np.ndarray) -> float:
        """Spectral decrease (energy drop from low to high freq)"""
        n_bins = magnitude.shape[0]
        
        # Divide into bands
        bands = [
            (0, n_bins // 4),
            (n_bins // 4, n_bins // 2),
            (n_bins // 2, 3 * n_bins // 4),
            (3 * n_bins // 4, n_bins)
        ]
        
        energies = []
        for start, end in bands:
            energies.append(np.mean(magnitude[start:end]))
        
        # Compute decrease ratio
        if energies[0] > 0:
            return float((energies[0] - energies[-1]) / energies[0])
        return 0.0
    
    def _compute_variation(self, magnitude: np.ndarray) -> float:
        """Spectral variation (change over time)"""
        if magnitude.shape[1] < 2:
            return 0.0
        
        # Compute frame-to-frame difference
        diff = np.diff(magnitude, axis=1)
        return float(np.mean(np.abs(diff)))
    
    def _lpc(self, audio: np.ndarray, order: int) -> np.ndarray:
        """Linear Predictive Coding coefficients"""
        # Autocorrelation method
        n = len(audio)
        
        # Compute autocorrelation
        autocorr = np.correlate(audio, audio, mode='full')
        autocorr = autocorr[n-1:n+order]
        
        # Solve Yule-Walker equations
        R = np.zeros((order, order))
        for i in range(order):
            for j in range(order):
                R[i, j] = autocorr[abs(i - j)]
        
        r = autocorr[1:order+1]
        
        try:
            coeffs = np.linalg.solve(R, r)
            return np.concatenate([[1], -coeffs])
        except np.linalg.LinAlgError:
            return np.ones(order + 1)
