# SPDX-License-Identifier: MIT

"""
Test fixtures and mock data for clawrtc testing.
Provides sample wallet data, mock API responses, hardware fingerprints,
and attestation flow scenarios for comprehensive testing.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class MockWalletFixtures:
    """Sample wallet data for testing"""

    VALID_WALLETS = [
        {
            "wallet_id": "test_wallet_001",
            "private_key": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
            "public_key": "04a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678901234567890abcdef1234567890abcdef1234567890abcdef123456",
            "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "balance_rtc": 150.75,
            "created_at": "2024-01-15T10:30:00Z"
        },
        {
            "wallet_id": "test_wallet_002",
            "private_key": "b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456a1",
            "public_key": "04b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678901234567890abcdef1234567890abcdef1234567890abcdef123456a1",
            "address": "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",
            "balance_rtc": 0.0,
            "created_at": "2024-02-01T14:22:33Z"
        },
        {
            "wallet_id": "miner_wallet_alpha",
            "private_key": "c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456a1b2",
            "public_key": "04c3d4e5f6789012345678901234567890abcdef1234567890abcdef12345678901234567890abcdef1234567890abcdef1234567890abcdef123456a1b2",
            "address": "1C7zdTfnkzmr13HfA2vRpyDJ2RgRP6kfXn",
            "balance_rtc": 2847.33,
            "miner_status": "active",
            "last_attestation": "2024-01-20T08:15:42Z"
        }
    ]

    INVALID_WALLETS = [
        {
            "wallet_id": "invalid_short",
            "private_key": "short",
            "error": "Invalid private key length"
        },
        {
            "wallet_id": "invalid_chars",
            "private_key": "xyz123invalid456chars789012345678901234567890abcdef1234567890abcdef",
            "error": "Invalid characters in private key"
        }
    ]


class MockAPIResponses:
    """Mock API response data for different endpoints"""

    @staticmethod
    def balance_success(wallet_id: str, amount: float = 100.0) -> Dict[str, Any]:
        return {
            "ok": True,
            "wallet_id": wallet_id,
            "amount_rtc": amount,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "network": "rustchain_mainnet"
        }

    @staticmethod
    def balance_not_found(wallet_id: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "Wallet not found",
            "wallet_id": wallet_id,
            "code": 404
        }

    @staticmethod
    def balance_server_error() -> Dict[str, Any]:
        return {
            "ok": False,
            "error": "Internal server error",
            "code": 500,
            "message": "Database connection failed"
        }

    @staticmethod
    def miner_registration_success(miner_id: str) -> Dict[str, Any]:
        return {
            "ok": True,
            "miner_id": miner_id,
            "status": "registered",
            "attestation_required": True,
            "next_attestation": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z",
            "registration_timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def attestation_challenge(miner_id: str) -> Dict[str, Any]:
        return {
            "ok": True,
            "miner_id": miner_id,
            "challenge": f"attest_{uuid.uuid4().hex}",
            "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat() + "Z",
            "required_proofs": ["hardware_fingerprint", "performance_benchmark", "network_connectivity"]
        }

    @staticmethod
    def attestation_success(miner_id: str, challenge: str) -> Dict[str, Any]:
        return {
            "ok": True,
            "miner_id": miner_id,
            "challenge": challenge,
            "attestation_status": "verified",
            "score": 85.7,
            "next_attestation": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
            "verified_at": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def attestation_failure(miner_id: str, reason: str = "Hardware verification failed") -> Dict[str, Any]:
        return {
            "ok": False,
            "miner_id": miner_id,
            "error": reason,
            "attestation_status": "failed",
            "retry_after": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        }


class HardwareFingerprintFixtures:
    """Sample hardware fingerprints for testing"""

    VALID_FINGERPRINTS = [
        {
            "fingerprint_id": "hw_fp_desktop_001",
            "cpu_model": "Intel Core i7-9700K",
            "cpu_cores": 8,
            "cpu_threads": 8,
            "cpu_frequency": 3600,
            "memory_total": 16384,
            "memory_available": 12288,
            "disk_total": 512000,
            "disk_free": 256000,
            "gpu_model": "NVIDIA GeForce RTX 3080",
            "gpu_memory": 10240,
            "os_type": "Windows",
            "os_version": "10.0.19045",
            "network_interfaces": ["Ethernet", "Wi-Fi"],
            "mac_addresses": ["00:1B:44:11:3A:B7", "A4:5E:60:C8:2B:9F"],
            "motherboard": "MSI MAG B460 TOMAHAWK",
            "bios_version": "7C82vA4",
            "timestamp": "2024-01-15T10:30:15Z",
            "hash": "a1b2c3d4e5f6789012345678901234567890abcdef"
        },
        {
            "fingerprint_id": "hw_fp_laptop_002",
            "cpu_model": "AMD Ryzen 5 4600H",
            "cpu_cores": 6,
            "cpu_threads": 12,
            "cpu_frequency": 3000,
            "memory_total": 8192,
            "memory_available": 6144,
            "disk_total": 256000,
            "disk_free": 128000,
            "gpu_model": "AMD Radeon Graphics",
            "gpu_memory": 512,
            "os_type": "Linux",
            "os_version": "Ubuntu 22.04.1",
            "network_interfaces": ["enp0s3", "wlp2s0"],
            "mac_addresses": ["08:00:27:12:34:56", "B8:27:EB:A1:B2:C3"],
            "motherboard": "HP 87D1",
            "bios_version": "F.22",
            "timestamp": "2024-02-01T14:45:30Z",
            "hash": "b2c3d4e5f6789012345678901234567890abcdef12"
        }
    ]

    SUSPICIOUS_FINGERPRINTS = [
        {
            "fingerprint_id": "hw_fp_vm_suspect",
            "cpu_model": "QEMU Virtual CPU version 2.5+",
            "cpu_cores": 2,
            "cpu_threads": 2,
            "memory_total": 4096,
            "disk_total": 50000,
            "os_type": "Linux",
            "virtualization_detected": True,
            "vm_indicators": ["VirtualBox", "VMware", "QEMU"],
            "risk_score": 8.5,
            "timestamp": "2024-01-10T09:15:22Z",
            "hash": "suspicious_vm_fingerprint_hash"
        }
    ]


class AttestationFlowFixtures:
    """Test scenarios for attestation flows"""

    SUCCESSFUL_FLOW = {
        "scenario": "successful_attestation",
        "steps": [
            {
                "step": 1,
                "action": "register_miner",
                "input": {"miner_id": "test_miner_001"},
                "expected_response": {
                    "ok": True,
                    "status": "registered",
                    "attestation_required": True
                }
            },
            {
                "step": 2,
                "action": "request_challenge",
                "input": {"miner_id": "test_miner_001"},
                "expected_response": {
                    "ok": True,
                    "challenge": "attest_challenge_token",
                    "expires_at": "2024-01-15T11:30:15Z"
                }
            },
            {
                "step": 3,
                "action": "submit_attestation",
                "input": {
                    "miner_id": "test_miner_001",
                    "challenge": "attest_challenge_token",
                    "hardware_proof": "hw_fingerprint_hash",
                    "performance_proof": {"score": 87.3, "benchmark_time": 45.2}
                },
                "expected_response": {
                    "ok": True,
                    "attestation_status": "verified",
                    "score": 87.3
                }
            }
        ]
    }

    HARDWARE_FAILURE_FLOW = {
        "scenario": "hardware_verification_failure",
        "steps": [
            {
                "step": 1,
                "action": "register_miner",
                "input": {"miner_id": "test_miner_002"},
                "expected_response": {"ok": True, "status": "registered"}
            },
            {
                "step": 2,
                "action": "request_challenge",
                "input": {"miner_id": "test_miner_002"},
                "expected_response": {"ok": True, "challenge": "attest_challenge_token"}
            },
            {
                "step": 3,
                "action": "submit_attestation",
                "input": {
                    "miner_id": "test_miner_002",
                    "challenge": "attest_challenge_token",
                    "hardware_proof": "suspicious_vm_fingerprint_hash"
                },
                "expected_response": {
                    "ok": False,
                    "error": "Hardware verification failed",
                    "attestation_status": "failed"
                }
            }
        ]
    }

    EXPIRED_CHALLENGE_FLOW = {
        "scenario": "expired_challenge",
        "steps": [
            {
                "step": 1,
                "action": "submit_attestation_with_expired_challenge",
                "input": {
                    "miner_id": "test_miner_003",
                    "challenge": "expired_challenge_token",
                    "hardware_proof": "valid_hw_fingerprint"
                },
                "expected_response": {
                    "ok": False,
                    "error": "Challenge expired",
                    "code": 400
                }
            }
        ]
    }


class NetworkTestFixtures:
    """Network connectivity and API endpoint test data"""

    ENDPOINTS = {
        "mainnet": {
            "base_url": "https://api.rustchain.com",
            "balance_endpoint": "/api/v1/balance",
            "attestation_endpoint": "/api/v1/miner/attest",
            "challenge_endpoint": "/api/v1/miner/challenge"
        },
        "testnet": {
            "base_url": "https://testnet-api.rustchain.com",
            "balance_endpoint": "/api/v1/balance",
            "attestation_endpoint": "/api/v1/miner/attest",
            "challenge_endpoint": "/api/v1/miner/challenge"
        },
        "local": {
            "base_url": "http://localhost:8080",
            "balance_endpoint": "/api/v1/balance",
            "attestation_endpoint": "/api/v1/miner/attest",
            "challenge_endpoint": "/api/v1/miner/challenge"
        }
    }

    TIMEOUT_SCENARIOS = [
        {"timeout": 1.0, "should_fail": True},
        {"timeout": 5.0, "should_fail": False},
        {"timeout": 30.0, "should_fail": False}
    ]

    HTTP_ERROR_CODES = [400, 401, 403, 404, 429, 500, 502, 503]


class PerformanceBenchmarkFixtures:
    """Performance benchmark test data"""

    BENCHMARK_RESULTS = [
        {
            "miner_id": "perf_test_001",
            "cpu_score": 87.3,
            "memory_score": 92.1,
            "disk_score": 78.9,
            "network_score": 95.2,
            "overall_score": 88.4,
            "benchmark_duration": 45.2,
            "timestamp": "2024-01-15T10:30:15Z"
        },
        {
            "miner_id": "perf_test_002",
            "cpu_score": 65.7,
            "memory_score": 71.3,
            "disk_score": 69.8,
            "network_score": 82.5,
            "overall_score": 72.3,
            "benchmark_duration": 52.8,
            "timestamp": "2024-01-16T11:22:33Z"
        }
    ]


def get_sample_wallet(wallet_id: Optional[str] = None) -> Dict[str, Any]:
    """Get a sample wallet by ID or return the first valid one"""
    if wallet_id:
        for wallet in MockWalletFixtures.VALID_WALLETS:
            if wallet["wallet_id"] == wallet_id:
                return wallet
    return MockWalletFixtures.VALID_WALLETS[0]


def get_mock_api_response(endpoint: str, success: bool = True, **kwargs) -> Dict[str, Any]:
    """Get mock API response for given endpoint"""
    if endpoint == "balance":
        if success:
            return MockAPIResponses.balance_success(kwargs.get("wallet_id", "test_wallet"), kwargs.get("amount", 100.0))
        else:
            return MockAPIResponses.balance_not_found(kwargs.get("wallet_id", "test_wallet"))
    elif endpoint == "attestation":
        if success:
            return MockAPIResponses.attestation_success(kwargs.get("miner_id", "test_miner"), kwargs.get("challenge", "test_challenge"))
        else:
            return MockAPIResponses.attestation_failure(kwargs.get("miner_id", "test_miner"))

    return {"ok": False, "error": "Unknown endpoint"}


def generate_test_fingerprint(device_type: str = "desktop") -> Dict[str, Any]:
    """Generate a test hardware fingerprint"""
    if device_type == "desktop":
        return HardwareFingerprintFixtures.VALID_FINGERPRINTS[0]
    elif device_type == "laptop":
        return HardwareFingerprintFixtures.VALID_FINGERPRINTS[1]
    elif device_type == "suspicious":
        return HardwareFingerprintFixtures.SUSPICIOUS_FINGERPRINTS[0]

    return HardwareFingerprintFixtures.VALID_FINGERPRINTS[0]
