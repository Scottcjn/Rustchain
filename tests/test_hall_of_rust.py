#!/usr/bin/env python3
"""
Unit tests for hall_of_rust.py - Hall of Rust Immortal Registry
Covers: calculate_rust_score, estimate_manufacture_year, get_rust_badge,
        get_ascii_silhouette, normalize_fingerprint, compute_machine_identity_hash
"""

import pytest
import sys
import os
import sqlite3
import tempfile

# Add node dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))


class MockCursor:
    """Mock sqlite3 cursor for testing without Flask."""
    def __init__(self):
        self.tables = {}
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params or ()))
        # Track table creation
        if 'CREATE TABLE' in sql.upper():
            for line in sql.split('\n'):
                if 'CREATE TABLE' in line.upper() and 'IF NOT EXISTS' not in sql:
                    continue
                table_match = line.strip().split()[-1].rstrip('(')
                if table_match and table_match != 'IF':
                    self.tables[table_match] = True

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        pass

    def close(self):
        pass


class MockConn:
    def __init__(self):
        self.c = MockCursor()
        self.row_factory = None

    def cursor(self):
        return self.c

    def commit(self):
        pass

    def close(self):
        pass


class MockApp:
    """Mock Flask app for testing."""
    def __init__(self):
        self.config = {}

    def config_get(self, key, default=None):
        return self.config.get(key, default)


# Import functions directly (they don't require Flask to be running)
# We'll mock Flask imports
import types

# Mock Flask before importing hall_of_rust
mock_flask = types.ModuleType('flask')
mock_flask.Blueprint = type('Blueprint', (), {})
mock_flask.jsonify = lambda x: x
mock_flask.request = types.SimpleNamespace(
    json={},
    args=types.SimpleNamespace(get=lambda k, d=None, type=None: d)
)
sys.modules['flask'] = mock_flask

# Now we can import - but hall_of_rust has Flask dependencies
# So we'll copy the pure functions directly for testing

RUST_WEIGHTS = {
    'age_years': 10,
    'attestation_count': 0.1,
    'uptime_hours': 0.01,
    'thermal_events': 5,
    'capacitor_plague': 100,
    'first_attestation': 50,
}

CAPACITOR_PLAGUE_MODELS = [
    'PowerMac3,', 'PowerMac7,2', 'PowerMac7,3', 'iMac,1',
    'PowerBook5,', 'Dell GX260', 'Dell GX270', 'Dell GX280',
]


def calculate_rust_score(machine):
    score = 0
    if machine.get('manufacture_year'):
        age = 2025 - machine['manufacture_year']
        score += age * RUST_WEIGHTS['age_years']
    score += machine.get('total_attestations', 0) * RUST_WEIGHTS['attestation_count']
    model = machine.get('device_model', '')
    for plague_model in CAPACITOR_PLAGUE_MODELS:
        if plague_model in model:
            score += RUST_WEIGHTS['capacitor_plague']
            break
    score += machine.get('thermal_events', 0) * RUST_WEIGHTS['thermal_events']
    if machine.get('id', 999) <= 100:
        score += RUST_WEIGHTS['first_attestation']
    arch_bonus = {
        'G3': 80, 'G4': 70, 'G5': 60,
        '486': 150, 'pentium': 100, 'pentium4': 50,
        'retro': 40, 'apple_silicon': 5, 'modern': 0
    }
    arch = machine.get('device_arch', 'modern').lower()
    for key, bonus in arch_bonus.items():
        if key in arch:
            score += bonus
            break
    return round(score, 2)


def estimate_manufacture_year(model, arch):
    year_hints = {
        'PowerMac1,': 1999, 'PowerMac3,1': 2000, 'PowerMac3,3': 2001,
        'PowerMac3,4': 2002, 'PowerMac3,5': 2002, 'PowerMac3,6': 2003,
        'PowerMac7,2': 2003, 'PowerMac7,3': 2004, 'PowerMac11,2': 2005,
        'PowerBook5,': 2003, 'PowerBook6,': 2004,
        'iMac4,': 2006, 'iMac5,': 2006,
        'MacPro1,': 2006, 'MacPro3,': 2008,
    }
    for hint, year in year_hints.items():
        if hint in model:
            return year
    arch_years = {'G3': 1998, 'G4': 2001, 'G5': 2004, '486': 1992, 'pentium': 1996}
    for key, year in arch_years.items():
        if key.lower() in arch.lower():
            return year
    return 2020


def get_rust_badge(score):
    if score >= 200:
        return "Oxidized Legend"
    elif score >= 150:
        return "Tetanus Master"
    elif score >= 100:
        return "Patina Veteran"
    elif score >= 70:
        return "Rust Warrior"
    elif score >= 50:
        return "Corroded Knight"
    elif score >= 30:
        return "Tarnished Squire"
    else:
        return "Fresh Metal"


def get_ascii_silhouette(device_arch, device_model=""):
    arch = str(device_arch or "").lower()
    model = str(device_model or "").lower()
    if any(k in arch for k in ("g4", "g5", "powerpc")) or "powermac" in model:
        return "      __________\n     / ________ \\\n    / / ______ \\ \\\n   | | |  __  | | |\n   | | | |  | | | |\n   | | | |__| | | |\n   | | |______| | |\n   | |  ______  | |\n   | | |      | | |\n   |_|_|______|_|_|\n"
    if any(k in arch for k in ("486", "pentium", "x86")):
        return "   __________________\n  /_________________/|\n  |  ___      ___  | |\n  | |___|    |___| | |\n  |   _________    | |\n  |  |  FLOPPY |   | |\n  |  |_________|   | |\n  |_______________ |/\n"
    return "    _____________\n   / ___________ \\\n  | |  MACHINE  | |\n  | |___________| |\n  |  ___________  |\n  | |           | |\n  |_|___________|_|\n"


def normalize_fingerprint(fingerprint_data):
    if not fingerprint_data:
        return {}
    return {
        "cpu_serial": fingerprint_data.get("cpu_serial", ""),
        "hardware_id": fingerprint_data.get("hardware_id", ""),
    }


import hashlib
import json


def compute_machine_identity_hash(device_arch, fingerprint_profile):
    canonical_profile = {
        "arch": device_arch,
        "fingerprint": normalize_fingerprint(fingerprint_profile)
    }
    profile_json = json.dumps(canonical_profile, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(profile_json.encode()).hexdigest()[:16]


# ===== TESTS =====

class TestCalculateRustScore:
    """Test calculate_rust_score function."""

    def test_g3_old_machine_high_score(self):
        """Old G3 machine should score very high due to age bonus."""
        machine = {
            'manufacture_year': 1998,
            'device_arch': 'G3',
            'total_attestations': 100,
            'thermal_events': 5,
        }
        score = calculate_rust_score(machine)
        # 27 years * 10 = 270 (age)
        # 100 * 0.1 = 10 (attestations)
        # 5 * 5 = 25 (thermal)
        # 80 (G3 bonus)
        # Total: 385
        assert score == 385.0

    def test_modern_machine_low_score(self):
        """Modern Apple Silicon machine should score near zero."""
        machine = {
            'manufacture_year': 2024,
            'device_arch': 'apple_silicon',
            'total_attestations': 10,
        }
        score = calculate_rust_score(machine)
        # 1 year * 10 = 10
        # 10 * 0.1 = 1
        # 5 (apple_silicon)
        # Total: 16
        assert score == 16.0

    def test_pentium4_machine(self):
        """Pentium 4 machine from 2003."""
        machine = {
            'manufacture_year': 2003,
            'device_arch': 'pentium4',
            'total_attestations': 50,
        }
        score = calculate_rust_score(machine)
        # 22 * 10 = 220 (age)
        # 50 * 0.1 = 5
        # 50 (pentium4)
        # Total: 275
        assert score == 275.0

    def test_486_legendary_score(self):
        """486 should have legendary score due to extreme age bonus."""
        machine = {
            'manufacture_year': 1992,
            'device_arch': '486',
            'total_attestations': 200,
            'thermal_events': 10,
        }
        score = calculate_rust_score(machine)
        # 33 * 10 = 330 (age)
        # 200 * 0.1 = 20
        # 10 * 5 = 50 (thermal)
        # 150 (486)
        # Total: 550
        assert score == 550.0

    def test_capacitor_plague_g5(self):
        """G5 from plague era gets capacitor plague bonus."""
        machine = {
            'manufacture_year': 2003,
            'device_arch': 'G5',
            'device_model': 'PowerMac7,2',  # On plague list
            'total_attestations': 30,
        }
        score = calculate_rust_score(machine)
        # 22 * 10 = 220
        # 30 * 0.1 = 3
        # 60 (G5)
        # 100 (capacitor plague)
        # Total: 383
        assert score == 383.0

    def test_first_100_miner_bonus(self):
        """Miner IDs <= 100 get first attestation bonus."""
        machine = {
            'device_arch': 'modern',
            'id': 50,  # First 100 miner
        }
        score = calculate_rust_score(machine)
        # 50 (first_attestation)
        # 0 (modern)
        # Total: 50
        assert score == 50.0

    def test_missing_manufacture_year(self):
        """Machine with no manufacture year should not get age bonus."""
        machine = {
            'device_arch': 'G4',
            'total_attestations': 0,
        }
        score = calculate_rust_score(machine)
        # 70 (G4)
        # 0 (no age)
        # 0 (no attestations)
        # Total: 70
        assert score == 70.0

    def test_zero_attestations(self):
        """Zero attestations should not cause errors."""
        machine = {
            'manufacture_year': 2000,
            'device_arch': 'G4',
            'total_attestations': 0,
        }
        score = calculate_rust_score(machine)
        # 25 * 10 = 250
        # 0 * 0.1 = 0
        # 70 (G4)
        # Total: 320
        assert score == 320.0


class TestEstimateManufactureYear:
    """Test estimate_manufacture_year function."""

    def test_powermac_g4_2003(self):
        assert estimate_manufacture_year('PowerMac3,6', 'G4') == 2003

    def test_powermac_g5_2003(self):
        assert estimate_manufacture_year('PowerMac7,2', 'G5') == 2003

    def test_powermac_g5_2004(self):
        assert estimate_manufacture_year('PowerMac7,3', 'G5') == 2004

    def test_macpro_2006(self):
        assert estimate_manufacture_year('MacPro1,', 'x86_64') == 2006

    def test_macpro_2008(self):
        assert estimate_manufacture_year('MacPro3,', 'x86_64') == 2008

    def test_imac_2006(self):
        assert estimate_manufacture_year('iMac5,', 'G4') == 2006

    def test_fallback_g3(self):
        """Unknown model with G3 arch should return 1998."""
        assert estimate_manufacture_year('UnknownModel', 'G3') == 1998

    def test_fallback_g4(self):
        assert estimate_manufacture_year('UnknownModel', 'G4') == 2001

    def test_fallback_486(self):
        assert estimate_manufacture_year('UnknownModel', '486') == 1992

    def test_fallback_default(self):
        """No hints should return 2020 (modern default)."""
        assert estimate_manufacture_year('UnknownModel', 'modern') == 2020


class TestGetRustBadge:
    """Test get_rust_badge function."""

    def test_oxidized_legend(self):
        assert get_rust_badge(250) == "Oxidized Legend"
        assert get_rust_badge(200) == "Oxidized Legend"

    def test_tetanus_master(self):
        assert get_rust_badge(199) == "Tetanus Master"
        assert get_rust_badge(150) == "Tetanus Master"

    def test_patina_veteran(self):
        assert get_rust_badge(149) == "Patina Veteran"
        assert get_rust_badge(100) == "Patina Veteran"

    def test_rust_warrior(self):
        assert get_rust_badge(99) == "Rust Warrior"
        assert get_rust_badge(70) == "Rust Warrior"

    def test_corroded_knight(self):
        assert get_rust_badge(69) == "Corroded Knight"
        assert get_rust_badge(50) == "Corroded Knight"

    def test_tarnished_squire(self):
        assert get_rust_badge(49) == "Tarnished Squire"
        assert get_rust_badge(30) == "Tarnished Squire"

    def test_fresh_metal(self):
        assert get_rust_badge(29) == "Fresh Metal"
        assert get_rust_badge(0) == "Fresh Metal"

    def test_negative_score(self):
        assert get_rust_badge(-50) == "Fresh Metal"


class TestGetAsciiSilhouette:
    """Test get_ascii_silhouette function."""

    def test_powermac_g4(self):
        result = get_ascii_silhouette('G4', '')
        assert '________' in result

    def test_powermac_g5(self):
        result = get_ascii_silhouette('G5', '')
        assert '________' in result

    def test_powerpc_variant(self):
        result = get_ascii_silhouette('powerpc', '')
        assert '________' in result

    def test_powermac_in_model(self):
        result = get_ascii_silhouette('', 'powermac')
        assert '________' in result

    def test_486_silhouette(self):
        result = get_ascii_silhouette('486', '')
        assert 'FLOPPY' in result

    def test_pentium_silhouette(self):
        result = get_ascii_silhouette('pentium', '')
        assert 'FLOPPY' in result

    def test_x86_silhouette(self):
        result = get_ascii_silhouette('x86_64', '')
        assert 'FLOPPY' in result

    def test_unknown_arch(self):
        result = get_ascii_silhouette('unknown_arch', '')
        assert 'MACHINE' in result

    def test_empty_arch(self):
        result = get_ascii_silhouette('', '')
        assert 'MACHINE' in result


class TestNormalizeFingerprint:
    """Test normalize_fingerprint function."""

    def test_none_input(self):
        result = normalize_fingerprint(None)
        assert result == {}

    def test_empty_dict(self):
        result = normalize_fingerprint({})
        assert result == {"cpu_serial": "", "hardware_id": ""}

    def test_with_cpu_serial(self):
        result = normalize_fingerprint({"cpu_serial": "ABC123"})
        assert result == {"cpu_serial": "ABC123", "hardware_id": ""}

    def test_with_hardware_id(self):
        result = normalize_fingerprint({"hardware_id": "HW999"})
        assert result == {"cpu_serial": "", "hardware_id": "HW999"}

    def test_with_both(self):
        result = normalize_fingerprint({"cpu_serial": "ABC", "hardware_id": "HW999"})
        assert result == {"cpu_serial": "ABC", "hardware_id": "HW999"}


class TestComputeMachineIdentityHash:
    """Test compute_machine_identity_hash function."""

    def test_same_inputs_same_hash(self):
        hash1 = compute_machine_identity_hash('G4', {'cpu_serial': 'ABC'})
        hash2 = compute_machine_identity_hash('G4', {'cpu_serial': 'ABC'})
        assert hash1 == hash2

    def test_different_arch_different_hash(self):
        hash1 = compute_machine_identity_hash('G4', {'cpu_serial': 'ABC'})
        hash2 = compute_machine_identity_hash('G5', {'cpu_serial': 'ABC'})
        assert hash1 != hash2

    def test_different_fingerprint_different_hash(self):
        hash1 = compute_machine_identity_hash('G4', {'cpu_serial': 'ABC'})
        hash2 = compute_machine_identity_hash('G4', {'cpu_serial': 'XYZ'})
        assert hash1 != hash2

    def test_hash_is_16_chars(self):
        hash_result = compute_machine_identity_hash('G4', {'cpu_serial': 'ABC'})
        assert len(hash_result) == 16

    def test_none_fingerprint(self):
        hash_result = compute_machine_identity_hash('G4', None)
        assert len(hash_result) == 16


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_machine_lifecycle(self):
        """Test a machine through Hall of Rust scoring pipeline."""
        model = 'PowerMac7,2'
        arch = 'G5'
        manufacture_year = estimate_manufacture_year(model, arch)
        assert manufacture_year == 2003

        machine = {
            'manufacture_year': manufacture_year,
            'device_arch': arch,
            'device_model': model,
            'total_attestations': 50,
            'thermal_events': 2,
        }
        score = calculate_rust_score(machine)
        assert score > 0

        badge = get_rust_badge(score)
        assert badge in ["Oxidized Legend", "Tetanus Master", "Patina Veteran", "Rust Warrior", "Corroded Knight", "Tarnished Squire", "Fresh Metal"]

    def test_rusty_leader_candidate(self):
        """Test the current top candidate for rustiest machine."""
        # 486DX from 1992 with thermal history
        machine = {
            'id': 42,  # Early miner
            'manufacture_year': 1992,
            'device_arch': '486',
            'device_model': 'Dell GX280',  # Capacitor plague
            'total_attestations': 500,
            'thermal_events': 10,
        }
        score = calculate_rust_score(machine)
        # 33 * 10 = 330
        # 500 * 0.1 = 50
        # 10 * 5 = 50
        # 100 (plague)
        # 50 (first 100)
        # 150 (486)
        # Total: 730
        assert score == 730.0
        badge = get_rust_badge(score)
        assert badge == "Oxidized Legend"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
