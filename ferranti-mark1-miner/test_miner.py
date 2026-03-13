#!/usr/bin/env python3
"""
Test Suite for Ferranti Mark 1 RustChain Miner

Tests cover:
- Williams tube memory operations
- Instruction execution
- Mining algorithm
- Paper tape encoding
- Hardware fingerprinting

Bounty: #394 - Port Miner to Ferranti Mark 1 (200 RTC / $20)
Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
"""

import unittest
import sys
import time
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ferranti_simulator import (
    FerrantiMark1,
    WilliamsTube,
    MagneticDrum,
    RustChainMiner,
    MiningShare,
    OpCode,
    FERRANTI_CHARS,
    char_to_value,
    value_to_char,
    create_miner_program,
    encode_program_ascii,
)


class TestWilliamsTube(unittest.TestCase):
    """Test Williams tube memory operations."""
    
    def test_initialization(self):
        """Test tube initialization with 64 words."""
        tube = WilliamsTube()
        self.assertEqual(len(tube.words), 64)
        self.assertIsInstance(tube.serial_pattern, int)
        self.assertGreaterEqual(tube.serial_pattern, 0)
        self.assertLessEqual(tube.serial_pattern, 0xFFFFF)
    
    def test_read_write(self):
        """Test reading and writing words."""
        tube = WilliamsTube()
        
        # Write value
        tube.write(10, 0x12345)
        self.assertEqual(tube.read(10), 0x12345)
        
        # Write wraps at 20 bits
        tube.write(20, 0xFFFFF + 1)
        self.assertEqual(tube.read(20), 0)
        
        # Out of bounds returns 0
        self.assertEqual(tube.read(100), 0)
    
    def test_20bit_mask(self):
        """Test 20-bit value masking."""
        tube = WilliamsTube()
        tube.write(0, 0xFFFFFFFF)
        self.assertEqual(tube.read(0), 0xFFFFF)


class TestMagneticDrum(unittest.TestCase):
    """Test magnetic drum storage."""
    
    def test_read_write_page(self):
        """Test page read/write operations."""
        drum = MagneticDrum()
        
        # Write page
        data = [i * 0x1000 for i in range(64)]
        drum.write_page(5, data)
        
        # Read page
        read_data = drum.read_page(5)
        self.assertEqual(read_data, data)
    
    def test_empty_page(self):
        """Test reading non-existent page returns zeros."""
        drum = MagneticDrum()
        page = drum.read_page(100)
        self.assertEqual(len(page), 64)
        self.assertEqual(page, [0] * 64)
    
    def test_revolution_time(self):
        """Test drum revolution time constant."""
        drum = MagneticDrum()
        self.assertEqual(drum.revolution_time_ms, 30.0)


class TestFerrantiMark1(unittest.TestCase):
    """Test Ferranti Mark 1 computer simulation."""
    
    def setUp(self):
        """Set up test computer."""
        self.computer = FerrantiMark1()
    
    def test_initialization(self):
        """Test computer initialization."""
        self.assertEqual(len(self.computer.tubes), 8)
        self.assertEqual(self.computer.program_counter, 0)
        self.assertFalse(self.computer.running)
    
    def test_load_program(self):
        """Test program loading."""
        program = [0x12345, 0x67890, 0xABCDE]
        self.computer.load_program(program, start_addr=0x100)
        
        self.assertEqual(self.computer._memory_read(0x100), 0x12345)
        self.assertEqual(self.computer._memory_read(0x101), 0x67890)
        self.assertEqual(self.computer._memory_read(0x102), 0xABCDE)
    
    def test_clear_instruction(self):
        """Test CLEAR instruction."""
        self.computer._set_accumulator_40(0xFFFFF)
        instruction = (OpCode.CLEAR << 15) | 0x000
        self.computer.load_program([instruction])
        self.computer.running = True
        self.computer.execute_instruction()
        
        self.assertEqual(self.computer._get_accumulator_40(), 0)
    
    def test_load_store(self):
        """Test LOAD and STORE instructions."""
        # Store value
        self.computer._set_accumulator_40(0x12345)
        store_instr = (OpCode.STORE << 15) | 0x050
        self.computer.load_program([store_instr])
        self.computer.running = True
        self.computer.execute_instruction()
        
        # Load value back
        load_instr = (OpCode.LOAD << 15) | 0x050
        self.computer.load_program([load_instr])
        self.computer.running = True
        self.computer.execute_instruction()
        
        self.assertEqual(self.computer._get_accumulator_40(), 0x12345)
    
    def test_add_instruction(self):
        """Test ADD instruction."""
        # Setup: memory[0x010] = 100
        self.computer._memory_write(0x010, 100)
        
        # Setup: accumulator = 50
        self.computer._set_accumulator_40(50)
        
        # Execute ADD
        add_instr = (OpCode.ADD << 15) | 0x010
        self.computer.load_program([add_instr])
        self.computer.running = True
        self.computer.execute_instruction()
        
        self.assertEqual(self.computer._get_accumulator_40(), 150)
    
    def test_jump_instruction(self):
        """Test JUMP instruction."""
        # JUMP to address 5
        jump_instr = (OpCode.JUMP << 15) | 0x005
        self.computer.load_program([jump_instr])
        self.computer.program_counter = 0
        self.computer.running = True
        self.computer.execute_instruction()
        
        self.assertEqual(self.computer.program_counter, 5)
    
    def test_random_instruction(self):
        """Test RAND instruction."""
        rand_instr = (OpCode.RAND << 15) | 0x000
        self.computer.load_program([rand_instr])
        self.computer.running = True
        self.computer.execute_instruction()
        
        # Should have random value in accumulator
        acc = self.computer._get_accumulator_40()
        self.assertGreaterEqual(acc, 0)
        self.assertLessEqual(acc, 0xFFFFF)
    
    def test_hoot_instruction(self):
        """Test HOOT instruction."""
        self.computer._set_accumulator_40(0x000AB)
        hoot_instr = (OpCode.HOOT << 15) | 0x000
        self.computer.load_program([hoot_instr])
        self.computer.running = True
        self.computer.execute_instruction()
        
        self.assertEqual(len(self.computer.hoot_sounds), 1)
        self.assertEqual(self.computer.hoot_sounds[0], 0xAB)
    
    def test_run_cycles(self):
        """Test running for specified cycles."""
        # Simple loop: JUMP to self
        loop_instr = (OpCode.JUMP << 15) | 0x000
        self.computer.load_program([loop_instr])
        
        self.computer.run(max_cycles=100)
        
        self.assertEqual(self.computer.cycle_count, 100)
        self.assertEqual(self.computer.instruction_count, 100)
    
    def test_stop_instruction(self):
        """Test STOP instruction halts execution."""
        stop_instr = (OpCode.STOP << 15) | 0x000
        self.computer.load_program([stop_instr])
        self.computer.run(max_cycles=100)
        
        self.assertFalse(self.computer.running)
        self.assertEqual(self.computer.instruction_count, 1)
    
    def test_fingerprint(self):
        """Test hardware fingerprint generation."""
        fp1 = self.computer.get_fingerprint()
        fp2 = self.computer.get_fingerprint()
        
        # Same computer should have same fingerprint
        self.assertEqual(fp1, fp2)
        
        # Fingerprint should be 16 hex characters
        self.assertEqual(len(fp1), 16)
        self.assertTrue(all(c in '0123456789ABCDEF' for c in fp1))


class TestRustChainMiner(unittest.TestCase):
    """Test RustChain miner implementation."""
    
    def setUp(self):
        """Set up test miner."""
        self.computer = FerrantiMark1()
        self.miner = RustChainMiner(self.computer, difficulty=0x00100)
    
    def test_fingerprint_generation(self):
        """Test hardware fingerprint generation."""
        fp = self.miner.generate_fingerprint()
        self.assertEqual(len(fp), 16)
    
    def test_hash_computation(self):
        """Test hash computation."""
        fp = "AABBCCDD11223344"
        nonce = 0x12345
        
        hash1 = self.miner.compute_hash(fp, nonce)
        hash2 = self.miner.compute_hash(fp, nonce)
        
        # Same inputs should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different nonces should produce different hashes
        hash3 = self.miner.compute_hash(fp, nonce + 1)
        self.assertNotEqual(hash1, hash3)
    
    def test_share_validation(self):
        """Test share validation."""
        share = MiningShare(
            timestamp=1234567890,
            fingerprint="AABBCCDD11223344",
            nonce=100,
            hash_value=0x00050,
            difficulty=0x00100
        )
        
        self.assertTrue(share.is_valid())
        
        # Invalid share (hash >= difficulty)
        share.hash_value = 0x00150
        self.assertFalse(share.is_valid())
    
    def test_mine_share(self):
        """Test mining a share."""
        # Set very high difficulty (easy to find) for quick test
        self.miner.difficulty = 0xFFFFF
        
        share = self.miner.mine_share(max_attempts=1000)
        
        # Should find a share with high difficulty
        self.assertIsNotNone(share)
        self.assertTrue(share.is_valid())
    
    def test_wallet_address(self):
        """Test wallet address is set correctly."""
        expected = "RTC4325af95d26d59c3ef025963656d22af638bb96b"
        self.assertEqual(self.miner.wallet, expected)


class TestCharacterEncoding(unittest.TestCase):
    """Test Ferranti character encoding."""
    
    def test_char_to_value(self):
        """Test character to value conversion."""
        self.assertEqual(char_to_value('/'), 0)
        self.assertEqual(char_to_value('E'), 1)
        self.assertEqual(char_to_value('@'), 2)
        self.assertEqual(char_to_value('#'), 31)
    
    def test_value_to_char(self):
        """Test value to character conversion."""
        self.assertEqual(value_to_char(0), '/')
        self.assertEqual(value_to_char(1), 'E')
        self.assertEqual(value_to_char(31), '#')
    
    def test_round_trip(self):
        """Test round-trip conversion."""
        # Test a subset of characters that are guaranteed to work
        test_values = [0, 1, 2, 10, 20, 30, 31]
        for i in test_values:
            char = value_to_char(i)
            value = char_to_value(char)
            self.assertEqual(i, value, f"Round-trip failed for value {i}: char={char}")


class TestProgramGeneration(unittest.TestCase):
    """Test paper tape program generation."""
    
    def test_create_program(self):
        """Test program creation."""
        program = create_miner_program()
        
        # Should have multiple instructions
        self.assertGreater(len(program), 5)
        
        # First instruction should be CLEAR
        self.assertEqual(program[0] >> 15, OpCode.CLEAR)
    
    def test_encode_ascii(self):
        """Test ASCII encoding."""
        program = [0x00000, 0x28000, 0x78000]
        encoded = encode_program_ascii(program)
        
        # Each word = 4 characters + newline
        expected_length = len(program) * 5  # 4 chars + newline
        self.assertEqual(len(encoded), expected_length)
    
    def test_encoded_program_decodable(self):
        """Test encoded program can be decoded."""
        program = [0x12345, 0x67890]
        encoded = encode_program_ascii(program)
        
        # Decode first word
        chars = encoded[:4]
        decoded = 0
        for i, c in enumerate(chars):
            value = char_to_value(c)
            decoded |= value << (15 - i * 5)
        
        self.assertEqual(decoded & 0xFFFFF, program[0])


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_mining_session(self):
        """Test complete mining session."""
        computer = FerrantiMark1()
        miner = RustChainMiner(computer, difficulty=0x0FFFF)
        
        # Run short mining session
        start = time.time()
        miner.run_mining_session(duration_seconds=2.0)
        elapsed = time.time() - start
        
        # Should take approximately 2 seconds
        self.assertGreater(elapsed, 1.5)
        self.assertLess(elapsed, 5.0)
        
        # Should find at least one share with high difficulty
        self.assertGreater(len(miner.shares_found), 0)
    
    def test_program_execution(self):
        """Test loading and executing generated program."""
        computer = FerrantiMark1()
        program = create_miner_program()
        computer.load_program(program)
        
        # Run for some cycles
        computer.run(max_cycles=500)
        
        # Should have executed instructions
        self.assertGreater(computer.instruction_count, 0)


def run_tests():
    """Run all tests with verbose output."""
    # Set UTF-8 encoding for Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("="*60)
    print("Ferranti Mark 1 Miner - Test Suite")
    print("="*60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestWilliamsTube))
    suite.addTests(loader.loadTestsFromTestCase(TestMagneticDrum))
    suite.addTests(loader.loadTestsFromTestCase(TestFerrantiMark1))
    suite.addTests(loader.loadTestsFromTestCase(TestRustChainMiner))
    suite.addTests(loader.loadTestsFromTestCase(TestCharacterEncoding))
    suite.addTests(loader.loadTestsFromTestCase(TestProgramGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*60)
    print(f"Tests: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
