#!/usr/bin/env python3
"""
Tests for Machine Passport Ledger (Issue #2309)

Comprehensive test suite covering:
- Passport CRUD operations
- Repair log management
- Attestation history tracking
- Benchmark signatures
- Lineage notes
- QR code generation
- PDF generation
- API endpoints
- Web viewer
"""

import os
import sys
import json
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from machine_passport import (
    MachinePassport,
    MachinePassportLedger,
    compute_machine_id,
    init_machine_passport_schema,
    generate_qr_code,
    generate_passport_pdf,
)


class TestMachinePassportDataStructure(unittest.TestCase):
    """Test the MachinePassport data structure."""
    
    def test_create_passport_minimal(self):
        """Test creating a passport with minimal fields."""
        passport = MachinePassport(
            machine_id='test123',
            name='Test Machine',
            owner_miner_id='miner_abc',
        )
        
        self.assertEqual(passport.machine_id, 'test123')
        self.assertEqual(passport.name, 'Test Machine')
        self.assertEqual(passport.owner_miner_id, 'miner_abc')
        self.assertIsNotNone(passport.created_at)
        self.assertIsNotNone(passport.updated_at)
    
    def test_create_passport_full(self):
        """Test creating a passport with all fields."""
        passport = MachinePassport(
            machine_id='test456',
            name='Old Faithful',
            owner_miner_id='miner_xyz',
            manufacture_year=1999,
            architecture='PowerPC G4',
            photo_hash='ipfs://QmTest123',
            photo_url='https://example.com/photo.jpg',
            provenance='eBay lot #12345',
        )
        
        self.assertEqual(passport.manufacture_year, 1999)
        self.assertEqual(passport.architecture, 'PowerPC G4')
        self.assertEqual(passport.provenance, 'eBay lot #12345')
    
    def test_passport_to_dict(self):
        """Test passport serialization."""
        passport = MachinePassport(
            machine_id='test789',
            name='Test',
            owner_miner_id='miner_abc',
            architecture='x86_64',
        )
        
        data = passport.to_dict()
        
        self.assertEqual(data['machine_id'], 'test789')
        self.assertEqual(data['name'], 'Test')
        self.assertEqual(data['architecture'], 'x86_64')
        self.assertIn('created_at', data)
    
    def test_passport_from_dict(self):
        """Test passport deserialization."""
        data = {
            'machine_id': 'test000',
            'name': 'Restored',
            'owner_miner_id': 'miner_def',
            'manufacture_year': 1995,
            'architecture': 'Pentium',
        }
        
        passport = MachinePassport.from_dict(data)
        
        self.assertEqual(passport.machine_id, 'test000')
        self.assertEqual(passport.manufacture_year, 1995)


class TestMachineIdComputation(unittest.TestCase):
    """Test machine ID computation from hardware fingerprints."""
    
    def test_compute_machine_id_deterministic(self):
        """Test that machine ID computation is deterministic."""
        fingerprint = {
            'cpu': 'PowerPC G4',
            'serial': 'ABC123',
            'macs': ['00:11:22:33:44:55'],
        }
        
        id1 = compute_machine_id(fingerprint)
        id2 = compute_machine_id(fingerprint)
        
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 16)  # 16 hex chars
    
    def test_compute_machine_id_different(self):
        """Test that different fingerprints produce different IDs."""
        fp1 = {'cpu': 'PowerPC G4', 'serial': 'ABC123'}
        fp2 = {'cpu': 'PowerPC G5', 'serial': 'ABC123'}
        
        id1 = compute_machine_id(fp1)
        id2 = compute_machine_id(fp2)
        
        self.assertNotEqual(id1, id2)


class TestMachinePassportLedger(unittest.TestCase):
    """Test the MachinePassportLedger class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.ledger = MachinePassportLedger(self.temp_db.name)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_create_passport(self):
        """Test creating a new passport."""
        passport = MachinePassport(
            machine_id='ledger_test_1',
            name='Test Machine',
            owner_miner_id='miner_test',
            architecture='TestArch',
        )
        
        success, msg = self.ledger.create_passport(passport)
        
        self.assertTrue(success)
        self.assertIn('created', msg.lower())
    
    def test_create_duplicate_passport(self):
        """Test that creating duplicate passport fails."""
        passport = MachinePassport(
            machine_id='dup_test',
            name='Test',
            owner_miner_id='miner_1',
        )
        
        self.ledger.create_passport(passport)
        
        # Try to create again
        success, msg = self.ledger.create_passport(passport)
        
        self.assertFalse(success)
        self.assertIn('already exists', msg.lower())
    
    def test_get_passport(self):
        """Test retrieving a passport."""
        passport = MachinePassport(
            machine_id='get_test',
            name='Get Test Machine',
            owner_miner_id='miner_get',
        )
        
        self.ledger.create_passport(passport)
        retrieved = self.ledger.get_passport('get_test')
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'Get Test Machine')
    
    def test_get_nonexistent_passport(self):
        """Test retrieving a nonexistent passport."""
        retrieved = self.ledger.get_passport('nonexistent')
        self.assertIsNone(retrieved)
    
    def test_update_passport(self):
        """Test updating a passport."""
        passport = MachinePassport(
            machine_id='update_test',
            name='Original Name',
            owner_miner_id='miner_orig',
        )
        
        self.ledger.create_passport(passport)
        
        success, msg = self.ledger.update_passport(
            'update_test',
            {'name': 'Updated Name', 'architecture': 'NewArch'}
        )
        
        self.assertTrue(success)
        
        updated = self.ledger.get_passport('update_test')
        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.architecture, 'NewArch')
    
    def test_delete_passport(self):
        """Test deleting a passport."""
        passport = MachinePassport(
            machine_id='delete_test',
            name='To Delete',
            owner_miner_id='miner_del',
        )
        
        self.ledger.create_passport(passport)
        success, msg = self.ledger.delete_passport('delete_test')
        
        self.assertTrue(success)
        self.assertIsNone(self.ledger.get_passport('delete_test'))
    
    def test_list_passports(self):
        """Test listing passports."""
        # Create multiple passports
        for i in range(5):
            passport = MachinePassport(
                machine_id=f'list_test_{i}',
                name=f'Test {i}',
                owner_miner_id='miner_list',
                architecture='ArchA' if i % 2 == 0 else 'ArchB',
            )
            self.ledger.create_passport(passport)

        # List all
        all_passports = self.ledger.list_passports(limit=10)
        self.assertEqual(len(all_passports), 5)

        # Filter by owner
        owner_filtered = self.ledger.list_passports(owner_miner_id='miner_list')
        self.assertEqual(len(owner_filtered), 5)

        # Filter by architecture (i=0,2,4 have ArchA = 3 passports)
        arch_filtered = self.ledger.list_passports(architecture='ArchA')
        self.assertEqual(len(arch_filtered), 3)  # i=0, 2, 4
    
    def test_repair_log(self):
        """Test repair log operations."""
        passport = MachinePassport(
            machine_id='repair_test',
            name='Repair Test',
            owner_miner_id='miner_rep',
        )
        self.ledger.create_passport(passport)
        
        # Add repair entry
        success, msg = self.ledger.add_repair_entry(
            machine_id='repair_test',
            repair_date=int(time.time()),
            repair_type='capacitor_replacement',
            description='Replaced all capacitors',
            parts_replaced='C1, C2, C3',
            technician='Tech Shop',
            cost_rtc=50000000,
        )
        
        self.assertTrue(success)
        
        # Get repair log
        log = self.ledger.get_repair_log('repair_test')
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]['repair_type'], 'capacitor_replacement')
    
    def test_attestation_history(self):
        """Test attestation history operations."""
        passport = MachinePassport(
            machine_id='attest_test',
            name='Attest Test',
            owner_miner_id='miner_att',
        )
        self.ledger.create_passport(passport)
        
        # Add attestation
        success, msg = self.ledger.add_attestation(
            machine_id='attest_test',
            attestation_ts=int(time.time()),
            epoch=100,
            total_epochs=50,
            total_rtc_earned=100000000,
            entropy_score=0.95,
        )
        
        self.assertTrue(success)
        
        # Get history
        history = self.ledger.get_attestation_history('attest_test')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['epoch'], 100)
    
    def test_benchmark_signatures(self):
        """Test benchmark signature operations."""
        passport = MachinePassport(
            machine_id='bench_test',
            name='Bench Test',
            owner_miner_id='miner_bench',
        )
        self.ledger.create_passport(passport)
        
        # Add benchmark
        success, msg = self.ledger.add_benchmark(
            machine_id='bench_test',
            benchmark_ts=int(time.time()),
            compute_score=1500.0,
            memory_bandwidth=3200.5,
            simd_identity='Altivec',
        )
        
        self.assertTrue(success)
        
        # Get benchmarks
        benchmarks = self.ledger.get_benchmark_signatures('bench_test')
        self.assertEqual(len(benchmarks), 1)
        self.assertEqual(benchmarks[0]['compute_score'], 1500.0)
    
    def test_lineage_notes(self):
        """Test lineage note operations."""
        passport = MachinePassport(
            machine_id='lineage_test',
            name='Lineage Test',
            owner_miner_id='miner_orig',
        )
        self.ledger.create_passport(passport)
        
        # Add lineage note (acquisition)
        success, msg = self.ledger.add_lineage_note(
            machine_id='lineage_test',
            lineage_ts=int(time.time()),
            event_type='acquisition',
            from_owner='previous_owner',
            to_owner='miner_orig',
            description='Acquired from vintage collector',
        )
        
        self.assertTrue(success)
        
        # Get lineage
        lineage = self.ledger.get_lineage_notes('lineage_test')
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]['event_type'], 'acquisition')
    
    def test_export_passport_full(self):
        """Test full passport export."""
        passport = MachinePassport(
            machine_id='export_test',
            name='Export Test',
            owner_miner_id='miner_exp',
        )
        self.ledger.create_passport(passport)
        
        # Add some data
        self.ledger.add_repair_entry(
            'export_test', int(time.time()), 'maintenance', 'General maintenance'
        )
        self.ledger.add_attestation('export_test', int(time.time()), epoch=1)
        
        # Export
        exported = self.ledger.export_passport_full('export_test')
        
        self.assertIsNotNone(exported)
        self.assertIn('passport', exported)
        self.assertIn('repair_log', exported)
        self.assertIn('attestation_history', exported)
        self.assertIn('exported_at', exported)


class TestQRCodeGeneration(unittest.TestCase):
    """Test QR code generation."""
    
    def test_generate_qr_code(self):
        """Test QR code generation."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp_path = tmp.name
        
        try:
            success, msg = generate_qr_code(
                'https://rustchain.org/passport/test123',
                tmp_path
            )
            
            # May fail if qrcode library not installed
            if success:
                self.assertTrue(os.path.exists(tmp_path))
                self.assertGreater(os.path.getsize(tmp_path), 0)
            else:
                self.assertIn('not available', msg.lower())
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestPDFGeneration(unittest.TestCase):
    """Test PDF generation."""
    
    def test_generate_passport_pdf(self):
        """Test PDF generation."""
        passport_data = {
            'passport': {
                'machine_id': 'pdf_test',
                'name': 'PDF Test Machine',
                'owner_miner_id': 'miner_pdf',
                'architecture': 'TestArch',
                'manufacture_year': 2000,
            },
            'repair_log': [
                {
                    'repair_date': int(time.time()),
                    'repair_type': 'test',
                    'description': 'Test repair',
                    'parts_replaced': 'None',
                }
            ],
            'attestation_history': [
                {
                    'attestation_ts': int(time.time()),
                    'epoch': 1,
                    'total_epochs': 10,
                    'total_rtc_earned': 50000000,
                }
            ],
            'benchmark_signatures': [],
            'lineage_notes': [],
        }
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp_path = tmp.name
        
        try:
            success, msg = generate_passport_pdf(passport_data, tmp_path)
            
            # May fail if reportlab library not installed
            if success:
                self.assertTrue(os.path.exists(tmp_path))
                self.assertGreater(os.path.getsize(tmp_path), 0)
            else:
                self.assertIn('not available', msg.lower())
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints."""
    
    def setUp(self):
        """Set up test Flask app."""
        from flask import Flask
        from machine_passport_api import machine_passport_bp

        self._prev_admin_key = os.environ.get('ADMIN_KEY')
        os.environ.pop('ADMIN_KEY', None)
        
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(machine_passport_bp)
        
        # Set test database
        import machine_passport_api
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        machine_passport_api.PASSPORT_DB_PATH = temp_db.name
        machine_passport_api._ledger = None
        
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up."""
        import machine_passport_api
        machine_passport_api._ledger = None
        if os.path.exists(machine_passport_api.PASSPORT_DB_PATH):
            os.unlink(machine_passport_api.PASSPORT_DB_PATH)
        if self._prev_admin_key is None:
            os.environ.pop('ADMIN_KEY', None)
        else:
            os.environ['ADMIN_KEY'] = self._prev_admin_key
    
    def test_list_passports_empty(self):
        """Test listing passports when empty."""
        resp = self.client.get('/api/machine-passport')
        data = json.loads(resp.data)
        
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['ok'])
        self.assertEqual(data['count'], 0)
    
    def test_create_passport(self):
        """Test creating a passport via API."""
        passport_data = {
            'name': 'API Test',
            'owner_miner_id': 'miner_api',
            'architecture': 'TestArch',
            'machine_id': 'api_test_001',  # Required field
        }

        resp = self.client.post(
            '/api/machine-passport',
            json=passport_data,
            # No admin key needed if ADMIN_KEY env var not set
        )
        data = json.loads(resp.data)

        # Should succeed (no admin key required if ADMIN_KEY not set)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(data['ok'])
        self.assertIn('machine_id', data)

    def test_update_passport_rejects_owner_claim_without_admin_key(self):
        """Client-supplied owner_miner_id is not proof of ownership."""
        self.client.post(
            '/api/machine-passport',
            json={
                'name': 'Owner Claim Test',
                'owner_miner_id': 'miner_owner',
                'machine_id': 'owner_claim_test',
            },
        )
        os.environ['ADMIN_KEY'] = 'expected-admin-key'

        with patch('hmac.compare_digest', return_value=False) as compare_digest:
            resp = self.client.put(
                '/api/machine-passport/owner_claim_test',
                headers={'X-Admin-Key': 'wrong-admin-key'},
                json={
                    'owner_miner_id': 'miner_owner',
                    'name': 'Unauthorized Rename',
                },
            )

        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'unauthorized')
        compare_digest.assert_called_once_with(b'wrong-admin-key', b'expected-admin-key')

        get_resp = self.client.get('/api/machine-passport/owner_claim_test')
        passport = json.loads(get_resp.data)['passport']['passport']
        self.assertEqual(passport['name'], 'Owner Claim Test')

    def test_update_passport_accepts_valid_admin_key(self):
        """Configured admin key still authorizes passport updates."""
        self.client.post(
            '/api/machine-passport',
            json={
                'name': 'Admin Update Test',
                'owner_miner_id': 'miner_owner',
                'machine_id': 'admin_update_test',
            },
        )
        os.environ['ADMIN_KEY'] = 'expected-admin-key'

        with patch('hmac.compare_digest', return_value=True) as compare_digest:
            resp = self.client.put(
                '/api/machine-passport/admin_update_test',
                headers={'X-Admin-Key': 'expected-admin-key'},
                json={'name': 'Authorized Rename'},
            )

        data = json.loads(resp.data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data['ok'])
        compare_digest.assert_called_once_with(b'expected-admin-key', b'expected-admin-key')
    
    def test_get_nonexistent_passport(self):
        """Test getting a nonexistent passport."""
        resp = self.client.get('/api/machine-passport/nonexistent')
        data = json.loads(resp.data)
        
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'passport_not_found')


class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.ledger = MachinePassportLedger(self.temp_db.name)
    
    def tearDown(self):
        """Clean up."""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_complete_passport_lifecycle(self):
        """Test complete passport lifecycle from creation to deletion."""
        # 1. Create passport
        passport = MachinePassport(
            machine_id='lifecycle_test',
            name='Old Faithful',
            owner_miner_id='miner_lifecycle',
            manufacture_year=1999,
            architecture='PowerPC G4',
            provenance='eBay lot #99999',
        )
        success, _ = self.ledger.create_passport(passport)
        self.assertTrue(success)
        
        # 2. Add repair history
        self.ledger.add_repair_entry(
            'lifecycle_test',
            int(time.time()) - 86400 * 30,  # 30 days ago
            'psu_recap',
            'Replaced all PSU capacitors',
            parts_replaced='470uF/16V x3, 1000uF/25V x2',
            technician='RetroRepair Shop',
            cost_rtc=75000000,
        )
        
        # 3. Add attestations over time
        for epoch in range(10, 20):
            self.ledger.add_attestation(
                'lifecycle_test',
                int(time.time()) - (20 - epoch) * 3600,
                epoch=epoch,
                total_epochs=epoch + 1,
                total_rtc_earned=(epoch + 1) * 10000000,
                entropy_score=0.9 + (epoch * 0.01),
            )
        
        # 4. Add benchmark signatures
        self.ledger.add_benchmark(
            'lifecycle_test',
            int(time.time()),
            cache_timing_profile='L1: 2 cycles, L2: 8 cycles',
            simd_identity='Altivec',
            compute_score=1250.5,
            memory_bandwidth=2800.0,
        )
        
        # 5. Add lineage note
        self.ledger.add_lineage_note(
            'lifecycle_test',
            int(time.time()) - 86400 * 60,  # 60 days ago
            'acquisition',
            from_owner='vintage_collector',
            to_owner='miner_lifecycle',
            description='Acquired from estate sale',
        )
        
        # 6. Export full passport
        exported = self.ledger.export_passport_full('lifecycle_test')
        
        self.assertIsNotNone(exported)
        self.assertEqual(exported['passport']['name'], 'Old Faithful')
        self.assertEqual(len(exported['repair_log']), 1)
        self.assertEqual(len(exported['attestation_history']), 10)
        self.assertEqual(len(exported['benchmark_signatures']), 1)
        self.assertEqual(len(exported['lineage_notes']), 1)
        
        # 7. Verify data integrity
        total_rtc = max(a['total_rtc_earned'] for a in exported['attestation_history'])
        self.assertEqual(total_rtc, 20 * 10000000)
        
        # 8. Update passport
        self.ledger.update_passport('lifecycle_test', {
            'name': 'Old Faithful (Upgraded)',
        })
        
        updated = self.ledger.get_passport('lifecycle_test')
        self.assertEqual(updated.name, 'Old Faithful (Upgraded)')


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMachinePassportDataStructure))
    suite.addTests(loader.loadTestsFromTestCase(TestMachineIdComputation))
    suite.addTests(loader.loadTestsFromTestCase(TestMachinePassportLedger))
    suite.addTests(loader.loadTestsFromTestCase(TestQRCodeGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestPDFGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_tests()
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
