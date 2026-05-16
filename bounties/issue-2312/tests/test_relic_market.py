#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Comprehensive tests for Rent-a-Relic Market API
Issue #2312
"""

import unittest
import json
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from relic_market_api import (
    VintageMachine, Reservation, ProvenanceReceipt,
    MachineRegistry, EscrowManager, ReceiptSigner,
    ReservationManager, MCPIntegration, BeaconIntegration,
    AccessDuration, ReservationStatus, app
)


class TestVintageMachine(unittest.TestCase):
    """Test VintageMachine dataclass"""
    
    def test_create_machine(self):
        machine = VintageMachine(
            machine_id="test-001",
            name="Test Machine",
            architecture="x86",
            cpu_model="Test CPU",
            cpu_speed_ghz=3.0,
            ram_gb=16,
            storage_gb=500,
            gpu_model="Test GPU",
            os="Linux",
            year=2020,
            manufacturer="Test Corp",
            description="Test description",
            photo_urls=["/test.jpg"],
            ssh_port=22,
            api_port=5000
        )
        
        self.assertEqual(machine.machine_id, "test-001")
        self.assertEqual(machine.name, "Test Machine")
        self.assertTrue(machine.is_available)
        self.assertEqual(machine.hourly_rate_rtc, 10.0)
    
    def test_machine_to_dict(self):
        machine = VintageMachine(
            machine_id="test-002",
            name="Test 2",
            architecture="ppc64",
            cpu_model="G5",
            cpu_speed_ghz=2.5,
            ram_gb=8,
            storage_gb=250,
            gpu_model=None,
            os="MacOS",
            year=2005,
            manufacturer="Apple",
            description="Desc",
            photo_urls=[],
            ssh_port=22,
            api_port=5000
        )
        
        d = machine.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['machine_id'], "test-002")
        self.assertEqual(d['architecture'], "ppc64")


class TestMachineRegistry(unittest.TestCase):
    """Test MachineRegistry"""
    
    def setUp(self):
        self.registry = MachineRegistry()
    
    def test_initialization(self):
        """Test registry initializes with sample machines"""
        machines = self.registry.list_machines()
        self.assertGreater(len(machines), 0)
    
    def test_list_machines_available_only(self):
        available = self.registry.list_machines(available_only=True)
        all_machines = self.registry.list_machines()
        
        self.assertLessEqual(len(available), len(all_machines))
        for m in available:
            self.assertTrue(m.is_available)
    
    def test_get_machine(self):
        machine = self.registry.get_machine("vm-001")
        self.assertIsNotNone(machine)
        self.assertEqual(machine.machine_id, "vm-001")
    
    def test_get_machine_not_found(self):
        machine = self.registry.get_machine("nonexistent")
        self.assertIsNone(machine)
    
    def test_update_uptime(self):
        initial_uptime = self.registry.get_machine("vm-001").uptime_hours
        self.registry.update_uptime("vm-001", 100)
        new_uptime = self.registry.get_machine("vm-001").uptime_hours
        self.assertEqual(new_uptime, initial_uptime + 100)
    
    def test_increment_reservations(self):
        initial_count = self.registry.get_machine("vm-001").total_reservations
        self.registry.increment_reservations("vm-001")
        new_count = self.registry.get_machine("vm-001").total_reservations
        self.assertEqual(new_count, initial_count + 1)
    
    def test_set_availability(self):
        self.registry.set_availability("vm-001", False)
        machine = self.registry.get_machine("vm-001")
        self.assertFalse(machine.is_available)
        
        self.registry.set_availability("vm-001", True)
        machine = self.registry.get_machine("vm-001")
        self.assertTrue(machine.is_available)


class TestEscrowManager(unittest.TestCase):
    """Test EscrowManager"""
    
    def setUp(self):
        self.escrow = EscrowManager()
    
    def test_lock_funds(self):
        tx_hash = self.escrow.lock_funds("res-001", "agent-123", 100.0)
        self.assertIsNotNone(tx_hash)
        self.assertEqual(len(tx_hash), 64)  # SHA256 hex
    
    def test_get_escrow(self):
        self.escrow.lock_funds("res-002", "agent-456", 50.0)
        escrow = self.escrow.get_escrow("res-002")
        
        self.assertIsNotNone(escrow)
        self.assertEqual(escrow['amount_rtc'], 50.0)
        self.assertEqual(escrow['status'], 'locked')
        self.assertFalse(escrow['released'])
    
    def test_release_funds(self):
        self.escrow.lock_funds("res-003", "agent-789", 75.0)
        result = self.escrow.release_funds("res-003", "operator-vm-001")
        
        self.assertTrue(result)
        escrow = self.escrow.get_escrow("res-003")
        self.assertTrue(escrow['released'])
        self.assertEqual(escrow['status'], 'released')
    
    def test_release_already_released(self):
        self.escrow.lock_funds("res-004", "agent-000", 25.0)
        self.escrow.release_funds("res-004", "operator")
        
        result = self.escrow.release_funds("res-004", "operator")
        self.assertFalse(result)
    
    def test_refund(self):
        self.escrow.lock_funds("res-005", "agent-refund", 60.0)
        result = self.escrow.refund("res-005")
        
        self.assertTrue(result)
        escrow = self.escrow.get_escrow("res-005")
        self.assertTrue(escrow['refunded'])
        self.assertEqual(escrow['status'], 'refunded')
    
    def test_get_nonexistent_escrow(self):
        escrow = self.escrow.get_escrow("nonexistent")
        self.assertIsNone(escrow)


class TestReceiptSigner(unittest.TestCase):
    """Test ReceiptSigner"""
    
    def setUp(self):
        self.signer = ReceiptSigner()
    
    def test_get_public_key(self):
        pub_key = self.signer.get_public_key("vm-001")
        self.assertIsNotNone(pub_key)
        self.assertEqual(len(pub_key), 64)  # Ed25519 public key hex
    
    def test_get_unknown_machine_key(self):
        pub_key = self.signer.get_public_key("unknown-machine")
        self.assertIsNone(pub_key)
    
    def test_sign_and_verify(self):
        data = {"test": "data", "timestamp": time.time()}
        signature = self.signer.sign_receipt(data, "vm-001")

        self.assertIsNotNone(signature)

        # Verify - use the same data that was signed (sign_receipt doesn't modify input)
        # The sign_receipt method creates canonical JSON with sort_keys=True
        is_valid = self.signer.verify_signature(data, signature, "vm-001")
        self.assertTrue(is_valid)
    
    def test_verify_tampered_data(self):
        data = {"test": "data", "timestamp": time.time()}
        signature = self.signer.sign_receipt(data, "vm-001")
        
        # Tamper with data
        data["test"] = "tampered"
        
        is_valid = self.signer.verify_signature(data, signature, "vm-001")
        self.assertFalse(is_valid)
    
    def test_verify_wrong_machine(self):
        data = {"test": "data"}
        signature = self.signer.sign_receipt(data, "vm-001")
        
        # Try to verify with different machine
        is_valid = self.signer.verify_signature(data, signature, "vm-002")
        self.assertFalse(is_valid)


class TestReservationManager(unittest.TestCase):
    """Test ReservationManager"""
    
    def setUp(self):
        self.registry = MachineRegistry()
        self.escrow = EscrowManager()
        self.signer = ReceiptSigner()
        self.manager = ReservationManager(self.registry, self.escrow, self.signer)
    
    def test_create_reservation(self):
        reservation, error = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-test",
            duration_hours=1,
            payment_rtc=50.0
        )
        
        self.assertIsNone(error)
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.machine_id, "vm-001")
        self.assertEqual(reservation.agent_id, "agent-test")
        self.assertEqual(reservation.duration_hours, 1)
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED.value)
    
    def test_create_reservation_machine_not_found(self):
        reservation, error = self.manager.create_reservation(
            machine_id="nonexistent",
            agent_id="agent-test",
            duration_hours=1,
            payment_rtc=50.0
        )
        
        self.assertEqual(error, "Machine not found")
        self.assertIsNone(reservation)
    
    def test_create_reservation_unavailable_machine(self):
        self.registry.set_availability("vm-001", False)
        
        reservation, error = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-test",
            duration_hours=1,
            payment_rtc=50.0
        )
        
        self.assertEqual(error, "Machine not available")
    
    def test_create_reservation_invalid_duration(self):
        reservation, error = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-test",
            duration_hours=5,  # Invalid
            payment_rtc=50.0
        )
        
        self.assertIsNotNone(error)
        self.assertIn("Invalid duration", error)
    
    def test_create_reservation_insufficient_payment(self):
        reservation, error = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-test",
            duration_hours=1,
            payment_rtc=1.0  # Too low
        )
        
        self.assertIsNotNone(error)
        self.assertIn("Insufficient payment", error)
    
    def test_start_session(self):
        reservation, _ = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-start",
            duration_hours=1,
            payment_rtc=50.0
        )
        
        error = self.manager.start_session(reservation.reservation_id)
        self.assertIsNone(error)
        
        updated = self.manager.get_reservation(reservation.reservation_id)
        self.assertEqual(updated.status, ReservationStatus.ACTIVE.value)
        self.assertIsNotNone(updated.access_granted_at)
    
    def test_complete_session(self):
        # Create and start reservation
        reservation, _ = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-complete",
            duration_hours=1,
            payment_rtc=50.0
        )
        self.manager.start_session(reservation.reservation_id)
        
        # Complete
        time.sleep(0.1)  # Small delay
        receipt, error = self.manager.complete_session(
            reservation_id=reservation.reservation_id,
            compute_hash="abc123",
            hardware_attestation={"cpu": "test", "verified": True}
        )
        
        self.assertIsNone(error)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.session_id, reservation.reservation_id)
        self.assertIsNotNone(receipt.signature)
    
    def test_get_receipt(self):
        reservation, _ = self.manager.create_reservation(
            machine_id="vm-001",
            agent_id="agent-receipt",
            duration_hours=1,
            payment_rtc=50.0
        )
        self.manager.start_session(reservation.reservation_id)
        receipt, _ = self.manager.complete_session(
            reservation.reservation_id,
            "hash123",
            {"attestation": "test"}
        )
        
        retrieved = self.manager.get_receipt(reservation.reservation_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.receipt_id, receipt.receipt_id)
    
    def test_get_agent_reservations(self):
        agent_id = "agent-multi"
        
        # Create multiple reservations
        self.manager.create_reservation("vm-001", agent_id, 1, 50.0)
        self.manager.create_reservation("vm-002", agent_id, 1, 15.0)
        
        reservations = self.manager.get_agent_reservations(agent_id)
        self.assertEqual(len(reservations), 2)
    
    def test_leaderboard(self):
        # Create reservations for different machines
        self.manager.create_reservation("vm-001", "agent-1", 1, 50.0)
        self.manager.create_reservation("vm-001", "agent-2", 1, 50.0)
        self.manager.create_reservation("vm-002", "agent-3", 1, 15.0)
        
        leaderboard = self.manager.get_most_rented_machines(limit=5)
        
        self.assertGreater(len(leaderboard), 0)
        # vm-001 should be first (2 rentals)
        self.assertEqual(leaderboard[0][0], "vm-001")
        self.assertEqual(leaderboard[0][1], 2)


class TestMCPIntegration(unittest.TestCase):
    """Test MCP Integration"""
    
    def setUp(self):
        registry = MachineRegistry()
        escrow = EscrowManager()
        signer = ReceiptSigner()
        manager = ReservationManager(registry, escrow, signer)
        self.mcp = MCPIntegration(manager)
    
    def test_get_manifest(self):
        manifest = self.mcp.get_mcp_manifest()
        
        self.assertEqual(manifest['mcpVersion'], '1.0.0')
        self.assertEqual(manifest['name'], 'rustchain-relic-market')
        self.assertIn('tools', manifest)
    
    def test_list_machines_tool(self):
        result = self.mcp.handle_tool_call("list_machines", {"available_only": True})
        
        self.assertIn('machines', result)
        self.assertIn('count', result)
    
    def test_reserve_machine_tool(self):
        result = self.mcp.handle_tool_call("reserve_machine", {
            "machine_id": "vm-001",
            "agent_id": "mcp-agent",
            "duration_hours": 1,
            "payment_rtc": 50.0
        })
        
        self.assertNotIn('error', result)
        self.assertIn('reservation', result)
    
    def test_unknown_tool(self):
        result = self.mcp.handle_tool_call("unknown_tool", {})
        self.assertIn('error', result)


class TestBeaconIntegration(unittest.TestCase):
    """Test Beacon Integration"""
    
    def setUp(self):
        registry = MachineRegistry()
        escrow = EscrowManager()
        signer = ReceiptSigner()
        manager = ReservationManager(registry, escrow, signer)
        self.beacon = BeaconIntegration(manager)
    
    def test_reserve_message(self):
        result = self.beacon.handle_message("RESERVE", {
            "machine_id": "vm-001",
            "agent_id": "beacon-agent",
            "duration_hours": 1,
            "payment_rtc": 50.0
        })
        
        self.assertEqual(result['status'], 'confirmed')
        self.assertIn('reservation_id', result)
    
    def test_cancel_message(self):
        # First reserve
        reserve_result = self.beacon.handle_message("RESERVE", {
            "machine_id": "vm-002",
            "agent_id": "cancel-agent",
            "duration_hours": 1,
            "payment_rtc": 15.0
        })
        
        # Then cancel
        result = self.beacon.handle_message("CANCEL", {
            "reservation_id": reserve_result['reservation_id']
        })
        
        self.assertEqual(result['status'], 'cancelled')
    
    def test_status_message(self):
        reserve_result = self.beacon.handle_message("RESERVE", {
            "machine_id": "vm-003",
            "agent_id": "status-agent",
            "duration_hours": 1,
            "payment_rtc": 8.0
        })
        
        result = self.beacon.handle_message("STATUS", {
            "reservation_id": reserve_result['reservation_id']
        })
        
        self.assertIn('reservation', result)
    
    def test_unknown_message_type(self):
        result = self.beacon.handle_message("UNKNOWN", {})
        self.assertIn('error', result)


class TestAPIEndpoints(unittest.TestCase):
    """Test Flask API endpoints"""
    
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
    
    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['service'], 'relic-market')
    
    def test_get_available_machines(self):
        response = self.client.get('/relic/available')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('machines', data)
        self.assertIn('count', data)
    
    def test_get_machine_details(self):
        response = self.client.get('/relic/vm-001')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('machine', data)
        self.assertEqual(data['machine']['machine_id'], 'vm-001')
    
    def test_get_machine_not_found(self):
        response = self.client.get('/relic/nonexistent')
        self.assertEqual(response.status_code, 404)
    
    def test_reserve_machine(self):
        payload = {
            "machine_id": "vm-001",
            "agent_id": "api-agent",
            "duration_hours": 1,
            "payment_rtc": 50.0
        }
        
        response = self.client.post(
            '/relic/reserve',
            json=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertTrue(data['ok'])
        self.assertIn('reservation', data)
    
    def test_reserve_machine_missing_fields(self):
        payload = {"machine_id": "vm-001"}
        
        response = self.client.post(
            '/relic/reserve',
            json=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_get_reservation(self):
        # Create reservation first
        create_response = self.client.post('/relic/reserve', json={
            "machine_id": "vm-002",
            "agent_id": "test-agent",
            "duration_hours": 1,
            "payment_rtc": 15.0
        })
        reservation_id = json.loads(create_response.data)['reservation']['reservation_id']
        
        # Get it
        response = self.client.get(f'/relic/reservation/{reservation_id}')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['reservation']['reservation_id'], reservation_id)
    
    def test_leaderboard(self):
        response = self.client.get('/relic/leaderboard?limit=5')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('leaderboard', data)
    
    def test_mcp_manifest(self):
        response = self.client.get('/mcp/manifest')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'rustchain-relic-market')
    
    def test_beacon_message(self):
        payload = {
            "type": "RESERVE",
            "payload": {
                "machine_id": "vm-003",
                "agent_id": "beacon-api-agent",
                "duration_hours": 1,
                "payment_rtc": 8.0
            }
        }
        
        response = self.client.post(
            '/beacon/message',
            json=payload,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'confirmed')

    def test_json_write_endpoints_reject_non_object_bodies(self):
        endpoints = [
            '/relic/reserve',
            '/relic/reservation/missing/complete',
            '/mcp/tool',
            '/beacon/message',
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint, json=["not", "an", "object"])

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()['error'], "JSON object required")

    def test_json_write_endpoints_reject_malformed_bodies(self):
        endpoints = [
            '/relic/reserve',
            '/relic/reservation/missing/complete',
            '/mcp/tool',
            '/beacon/message',
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    data="{",
                    content_type='application/json',
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()['error'], "JSON object required")

    def test_json_write_endpoints_reject_missing_bodies(self):
        endpoints = [
            '/relic/reserve',
            '/relic/reservation/missing/complete',
            '/mcp/tool',
            '/beacon/message',
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(endpoint)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()['error'], "Request body required")

    def test_leaderboard_rejects_invalid_limits(self):
        for limit in ['abc', '0', '-1']:
            with self.subTest(limit=limit):
                response = self.client.get(f'/relic/leaderboard?limit={limit}')

                self.assertEqual(response.status_code, 400)


class TestAccessDuration(unittest.TestCase):
    """Test AccessDuration enum"""
    
    def test_valid_durations(self):
        self.assertEqual(AccessDuration.ONE_HOUR.value, 1)
        self.assertEqual(AccessDuration.FOUR_HOURS.value, 4)
        self.assertEqual(AccessDuration.TWENTY_FOUR_HOURS.value, 24)


class TestReservationStatus(unittest.TestCase):
    """Test ReservationStatus enum"""
    
    def test_status_values(self):
        self.assertEqual(ReservationStatus.PENDING.value, "pending")
        self.assertEqual(ReservationStatus.CONFIRMED.value, "confirmed")
        self.assertEqual(ReservationStatus.ACTIVE.value, "active")
        self.assertEqual(ReservationStatus.COMPLETED.value, "completed")
        self.assertEqual(ReservationStatus.CANCELLED.value, "cancelled")
        self.assertEqual(ReservationStatus.EXPIRED.value, "expired")


def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestVintageMachine))
    suite.addTests(loader.loadTestsFromTestCase(TestMachineRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestEscrowManager))
    suite.addTests(loader.loadTestsFromTestCase(TestReceiptSigner))
    suite.addTests(loader.loadTestsFromTestCase(TestReservationManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestBeaconIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestAccessDuration))
    suite.addTests(loader.loadTestsFromTestCase(TestReservationStatus))
    
    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
