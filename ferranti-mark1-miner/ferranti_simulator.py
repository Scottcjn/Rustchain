#!/usr/bin/env python3
"""
Ferranti Mark 1 Simulator with RustChain Proof-of-Antiquity Miner

This simulator emulates the core architecture of the Ferranti Mark 1 (1951)
and implements a conceptual RustChain miner adapted for vintage hardware.

Ferranti Mark 1 Specifications:
- 20-bit word size (instructions)
- 40-bit data words
- 512 words main memory (8 Williams tubes × 64 lines)
- 80-bit accumulator
- 40-bit MQ register
- 8 B-lines (index registers)
- ~50 instructions

Author: RustChain Contributor
Bounty: #394 - Port Miner to Ferranti Mark 1 (200 RTC / $20)
Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
"""

import random
import time
import argparse
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from enum import IntEnum
import sys


# ============================================================================
# Ferranti Mark 1 Character Encoding (5-bit Baudot)
# ============================================================================

# Ferranti character mapping (5-bit Baudot code)
# Note: Using ASCII-safe characters for compatibility
# Original: /E@A:SIU½DRJNFCKTZLWHYPQOBG"MXV£ (32 unique chars)
# Modified for ASCII compatibility (32 unique chars)
FERRANTI_CHARS = "/E@A:SIUHDRJNFCKTZLWY1234567890#"

def char_to_value(c: str) -> int:
    """Convert Ferranti character to 5-bit value."""
    try:
        return FERRANTI_CHARS.index(c)
    except ValueError:
        return 0

def value_to_char(v: int) -> str:
    """Convert 5-bit value to Ferranti character."""
    return FERRANTI_CHARS[v & 0x1F]


# ============================================================================
# Instruction Set
# ============================================================================

class OpCode(IntEnum):
    """Ferranti Mark 1 Operation Codes (simplified)."""
    STOP = 0b00000      # Stop the machine
    LOAD = 0b00001      # Load accumulator from memory
    STORE = 0b00010     # Store accumulator to memory
    ADD = 0b00011       # Add memory to accumulator
    SUB = 0b00100       # Subtract memory from accumulator
    MUL = 0b00101       # Multiply by memory
    DIV = 0b00110       # Divide by memory
    JUMP = 0b00111      # Unconditional jump
    JNEG = 0b01000      # Jump if accumulator negative
    JZER = 0b01001      # Jump if accumulator zero
    LOAD_B = 0b01010    # Load B-line
    ADD_B = 0b01011     # Add B-line to address
    INPUT = 0b01100     # Input from paper tape
    OUTPUT = 0b01101    # Output to paper tape
    HOOT = 0b01110      # Hoot command (audio output)
    RAND = 0b01111      # Random number
    AND = 0b10000       # Logical AND
    OR = 0b10001        # Logical OR
    NOT = 0b10010       # Logical NOT
    SHIFT_L = 0b10011   # Shift left
    SHIFT_R = 0b10100   # Shift right
    TEST = 0b10101      # Test bit
    CLEAR = 0b10110     # Clear accumulator
    LOAD_MQ = 0b10111   # Load MQ register
    STORE_MQ = 0b11000  # Store MQ register
    ADD_MQ = 0b11001    # Add MQ to accumulator


# ============================================================================
# Hardware Components
# ============================================================================

@dataclass
class WilliamsTube:
    """Represents a Williams tube memory unit (64 words)."""
    words: List[int] = field(default_factory=lambda: [0] * 64)
    serial_pattern: int = 0  # Unique pattern for fingerprinting
    
    def __post_init__(self):
        # Initialize with random "residual charge" pattern
        self.serial_pattern = random.randint(0, 0xFFFFF)
    
    def read(self, addr: int) -> int:
        """Read word from tube."""
        if 0 <= addr < 64:
            return self.words[addr]
        return 0
    
    def write(self, addr: int, value: int):
        """Write word to tube."""
        if 0 <= addr < 64:
            self.words[addr] = value & 0xFFFFF  # 20-bit mask


@dataclass
class MagneticDrum:
    """Represents the magnetic drum secondary storage (512 pages)."""
    pages: Dict[int, List[int]] = field(default_factory=dict)
    revolution_time_ms: float = 30.0
    
    def read_page(self, page_num: int) -> List[int]:
        """Read a page from drum."""
        if page_num not in self.pages:
            self.pages[page_num] = [0] * 64
        return self.pages[page_num].copy()
    
    def write_page(self, page_num: int, data: List[int]):
        """Write a page to drum."""
        self.pages[page_num] = [w & 0xFFFFF for w in data[:64]]


class FerrantiMark1:
    """
    Ferranti Mark 1 Computer Simulator
    
    Implements core architecture:
    - 8 Williams tubes (512 words total)
    - 80-bit accumulator (as two 40-bit halves)
    - 40-bit MQ register
    - 8 B-lines (index registers)
    - Magnetic drum storage
    - Paper tape I/O
    """
    
    def __init__(self):
        # Main memory: 8 Williams tubes
        self.tubes = [WilliamsTube() for _ in range(8)]
        
        # Secondary storage
        self.drum = MagneticDrum()
        
        # Registers
        self.accumulator_high = 0  # Upper 40 bits
        self.accumulator_low = 0   # Lower 40 bits
        self.mq_register = 0       # 40-bit MQ
        self.b_lines = [0] * 8     # Index registers
        self.program_counter = 0
        self.running = False
        
        # I/O
        self.paper_tape_output: List[str] = []
        self.hoot_sounds: List[int] = []
        
        # Statistics
        self.cycle_count = 0
        self.instruction_count = 0
    
    def _get_accumulator(self) -> int:
        """Get full 80-bit accumulator as integer."""
        return (self.accumulator_high << 40) | self.accumulator_low
    
    def _set_accumulator(self, value: int):
        """Set 80-bit accumulator from integer."""
        value = value & 0xFFFFFFFFFF  # 80-bit mask
        self.accumulator_high = (value >> 40) & 0xFFFFFFFFF
        self.accumulator_low = value & 0xFFFFFFFFF
    
    def _get_accumulator_40(self) -> int:
        """Get lower 40 bits of accumulator."""
        return self.accumulator_low
    
    def _set_accumulator_40(self, value: int):
        """Set lower 40 bits of accumulator."""
        self.accumulator_low = value & 0xFFFFFFFFF
    
    def _memory_read(self, addr: int) -> int:
        """Read from main memory (20-bit word)."""
        tube_num = (addr >> 6) & 0x07  # Bits 6-8 select tube
        line_num = addr & 0x3F          # Bits 0-5 select line
        return self.tubes[tube_num].read(line_num)
    
    def _memory_write(self, addr: int, value: int):
        """Write to main memory (20-bit word)."""
        tube_num = (addr >> 6) & 0x07
        line_num = addr & 0x3F
        self.tubes[tube_num].write(line_num, value)
    
    def _effective_address(self, addr: int) -> int:
        """Calculate effective address using B-lines."""
        # B-line modification (simplified - uses B0 by default)
        return (addr + self.b_lines[0]) & 0x1FF
    
    def load_program(self, program: List[int], start_addr: int = 0):
        """Load a program into memory."""
        for i, word in enumerate(program):
            self._memory_write(start_addr + i, word)
    
    def execute_instruction(self) -> bool:
        """Execute one instruction. Returns False if STOP."""
        if not self.running:
            return False
        
        # Fetch instruction
        instruction = self._memory_read(self.program_counter)
        self.program_counter = (self.program_counter + 1) & 0x1FF
        
        # Decode
        opcode = (instruction >> 15) & 0x1F  # Bits 15-19
        address = instruction & 0x7FFF        # Bits 0-14
        
        # Execute
        self._execute_opcode(opcode, address)
        
        self.instruction_count += 1
        self.cycle_count += 1
        
        return self.running
    
    def _execute_opcode(self, opcode: int, address: int):
        """Execute a specific opcode."""
        eff_addr = self._effective_address(address)
        
        if opcode == OpCode.STOP:
            self.running = False
        
        elif opcode == OpCode.LOAD:
            value = self._memory_read(eff_addr)
            self._set_accumulator_40(value)
        
        elif opcode == OpCode.STORE:
            value = self._get_accumulator_40()
            self._memory_write(eff_addr, value)
        
        elif opcode == OpCode.ADD:
            value = self._memory_read(eff_addr)
            self._set_accumulator_40(self._get_accumulator_40() + value)
        
        elif opcode == OpCode.SUB:
            value = self._memory_read(eff_addr)
            self._set_accumulator_40(self._get_accumulator_40() - value)
        
        elif opcode == OpCode.MUL:
            value = self._memory_read(eff_addr)
            result = self._get_accumulator_40() * value
            self._set_accumulator(result)  # 80-bit result
        
        elif opcode == OpCode.JUMP:
            self.program_counter = eff_addr
        
        elif opcode == OpCode.JNEG:
            if self._get_accumulator_40() & 0x80000:  # Sign bit
                self.program_counter = eff_addr
        
        elif opcode == OpCode.JZER:
            if self._get_accumulator_40() == 0:
                self.program_counter = eff_addr
        
        elif opcode == OpCode.LOAD_B:
            b_line = (address >> 10) & 0x07
            value = address & 0x3FF
            self.b_lines[b_line] = value
        
        elif opcode == OpCode.ADD_B:
            b_line = (address >> 10) & 0x07
            self.b_lines[b_line] = (self.b_lines[b_line] + 1) & 0x3FF
        
        elif opcode == OpCode.INPUT:
            # Simulated paper tape input
            value = random.randint(0, 0xFFFFF)
            self._set_accumulator_40(value)
        
        elif opcode == OpCode.OUTPUT:
            # Output accumulator to paper tape
            value = self._get_accumulator_40() & 0x1F
            char = value_to_char(value)
            self.paper_tape_output.append(char)
            print(f"[PAPER TAPE] {char}", file=sys.stderr)
        
        elif opcode == OpCode.HOOT:
            # Hoot command - audio output
            pitch = self._get_accumulator_40() & 0xFF
            self.hoot_sounds.append(pitch)
            print(f"[HOOT] ♫ Pitch {pitch}", file=sys.stderr)
        
        elif opcode == OpCode.RAND:
            # Random number instruction
            value = random.randint(0, 0xFFFFF)
            self._set_accumulator_40(value)
        
        elif opcode == OpCode.CLEAR:
            self._set_accumulator(0)
        
        elif opcode == OpCode.LOAD_MQ:
            value = self._memory_read(eff_addr)
            self.mq_register = value
        
        elif opcode == OpCode.STORE_MQ:
            self._memory_write(eff_addr, self.mq_register & 0xFFFFF)
        
        else:
            # Unknown opcode - treat as NOP
            pass
    
    def run(self, max_cycles: int = 1000) -> bool:
        """Run the machine for up to max_cycles."""
        self.running = True
        self.cycle_count = 0
        
        while self.running and self.cycle_count < max_cycles:
            self.execute_instruction()
        
        return self.running
    
    def get_fingerprint(self) -> str:
        """Generate hardware fingerprint from tube patterns."""
        patterns = [tube.serial_pattern for tube in self.tubes]
        fingerprint = sum(patterns) & 0xFFFFFFFFFFFFFFFF
        return f"{fingerprint:016X}"


# ============================================================================
# RustChain Proof-of-Antiquity Miner for Ferranti Mark 1
# ============================================================================

@dataclass
class MiningShare:
    """Represents a mining share."""
    timestamp: int
    fingerprint: str
    nonce: int
    hash_value: int
    difficulty: int
    
    def is_valid(self) -> bool:
        """Check if share meets difficulty."""
        return self.hash_value < self.difficulty


class RustChainMiner:
    """
    RustChain PoA Miner adapted for Ferranti Mark 1
    
    This is a conceptual implementation that demonstrates how
    Proof-of-Antiquity could work on vintage hardware.
    """
    
    def __init__(self, computer: FerrantiMark1, difficulty: int = 0x000FF):
        self.computer = computer
        self.difficulty = difficulty
        self.shares_found: List[MiningShare] = []
        self.nonce = 0
        self.wallet = "RTC4325af95d26d59c3ef025963656d22af638bb96b"
    
    def generate_fingerprint(self) -> str:
        """Generate hardware attestation fingerprint."""
        return self.computer.get_fingerprint()
    
    def compute_hash(self, fingerprint: str, nonce: int) -> int:
        """
        Compute hash for proof-of-work.
        
        On Ferranti Mark 1, we use a simplified hash:
        hash = (fingerprint XOR nonce) mod 2^20
        """
        fp_int = int(fingerprint, 16)
        hash_value = (fp_int ^ nonce) & 0xFFFFF
        return hash_value
    
    def mine_share(self, max_attempts: int = 10000) -> Optional[MiningShare]:
        """
        Attempt to find a valid mining share.
        
        Returns None if no share found within max_attempts.
        """
        fingerprint = self.generate_fingerprint()
        
        for _ in range(max_attempts):
            self.nonce = (self.nonce + 1) & 0xFFFFF
            
            # Compute hash
            hash_value = self.compute_hash(fingerprint, self.nonce)
            
            # Check difficulty
            if hash_value < self.difficulty:
                share = MiningShare(
                    timestamp=int(time.time()),
                    fingerprint=fingerprint,
                    nonce=self.nonce,
                    hash_value=hash_value,
                    difficulty=self.difficulty
                )
                self.shares_found.append(share)
                return share
        
        return None
    
    def submit_share(self, share: MiningShare):
        """Simulate submitting a share to the network."""
        print(f"\n{'='*60}")
        print("SHARE FOUND!")
        print(f"{'='*60}")
        print(f"Wallet:     {self.wallet}")
        print(f"Fingerprint: {share.fingerprint}")
        print(f"Nonce:      {share.nonce:05X}")
        print(f"Hash:       {share.hash_value:05X}")
        print(f"Difficulty: {share.difficulty:05X}")
        print(f"Timestamp:  {share.timestamp}")
        print(f"{'='*60}")
        
        # Output via paper tape (simulated)
        self.computer.paper_tape_output.append("SHARE")
        
        # Hoot sound (proof of work audio)
        self.computer.hoot_sounds.append(share.nonce & 0xFF)
    
    def run_mining_session(self, duration_seconds: float = 10.0):
        """Run a mining session for specified duration."""
        print(f"\n[MINER] Starting RustChain Mining Session on Ferranti Mark 1")
        print(f"Difficulty: 0x{self.difficulty:05X}")
        print(f"Duration:   {duration_seconds}s")
        print(f"Wallet:     {self.wallet}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        attempts = 0
        
        while (time.time() - start_time) < duration_seconds:
            # Run some computer cycles
            self.computer.run(max_cycles=100)
            
            # Attempt to mine
            share = self.mine_share(max_attempts=100)
            
            if share:
                self.submit_share(share)
                # Reset nonce after finding share
                self.nonce = 0
            
            attempts += 100
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*60}")
        print("MINING SESSION COMPLETE")
        print(f"{'='*60}")
        print(f"Duration:     {elapsed:.2f}s")
        print(f"Attempts:     {attempts}")
        print(f"Shares Found: {len(self.shares_found)}")
        print(f"Instructions: {self.computer.instruction_count}")
        print(f"Cycles:       {self.computer.cycle_count}")
        print(f"{'='*60}\n")


# ============================================================================
# Sample Paper Tape Program
# ============================================================================

def create_miner_program() -> List[int]:
    """
    Create a paper tape program for the Ferranti Mark 1 miner.
    
    This program implements the simplified mining algorithm:
    1. Read tube pattern
    2. XOR with nonce
    3. Check difficulty
    4. Output share if found
    5. Increment nonce and repeat
    """
    program = []
    
    # Address 000: Initialize
    # CLEAR accumulator
    program.append((OpCode.CLEAR << 15) | 0x000)  # 0x00000
    
    # Address 001: Load nonce from B-line 0
    program.append((OpCode.LOAD_B << 15) | 0x000)  # B0 = 0
    
    # Address 002: Load tube pattern (simulated)
    program.append((OpCode.RAND << 15) | 0x000)   # Random = tube pattern
    
    # Address 003: Store pattern
    program.append((OpCode.STORE << 15) | 0x010)  # Store at addr 0x010
    
    # Address 004: Mining loop start
    # ADD_B to increment nonce
    program.append((OpCode.ADD_B << 15) | 0x000)  # B0++
    
    # Address 005: Load pattern
    program.append((OpCode.LOAD << 15) | 0x010)   # Load pattern
    
    # Address 006: XOR with nonce (simulated via ADD)
    program.append((OpCode.ADD << 15) | 0x000)    # Add B0 (XOR approx)
    
    # Address 007: Check difficulty (JNEG if hash < 0)
    program.append((OpCode.JNEG << 15) | 0x00A)   # Jump to output if negative
    
    # Address 008: Continue loop
    program.append((OpCode.JUMP << 15) | 0x004)   # Jump back to loop
    
    # Address 009: (unused)
    program.append(0x00000)
    
    # Address 00A: Output share
    program.append((OpCode.OUTPUT << 15) | 0x000)  # Output result
    program.append((OpCode.HOOT << 15) | 0x000)    # Hoot!
    
    # Address 00B: Reset and continue
    program.append((OpCode.CLEAR << 15) | 0x000)
    program.append((OpCode.JUMP << 15) | 0x004)    # Continue mining
    
    # Address 00C: STOP (optional)
    program.append((OpCode.STOP << 15) | 0x000)
    
    return program


def encode_program_ascii(program: List[int]) -> str:
    """Encode program as ASCII using Ferranti character mapping."""
    result = []
    for word in program:
        # Each 20-bit word = 4 × 5-bit characters
        for i in range(4):
            char_value = (word >> (15 - i * 5)) & 0x1F
            result.append(value_to_char(char_value))
        result.append('\n')
    return ''.join(result)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Ferranti Mark 1 Simulator with RustChain PoA Miner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --run --cycles 1000
  %(prog)s --mine --duration 30 --difficulty 0x00100
  %(prog)s --program --output paper_tape.txt
  %(prog)s --demo

Bounty: #394 - Port Miner to Ferranti Mark 1 (200 RTC / $20)
Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
        '''
    )
    
    parser.add_argument('--run', action='store_true',
                       help='Run simulator with loaded program')
    parser.add_argument('--mine', action='store_true',
                       help='Run mining session')
    parser.add_argument('--program', action='store_true',
                       help='Generate paper tape program')
    parser.add_argument('--demo', action='store_true',
                       help='Run demonstration')
    
    parser.add_argument('--cycles', type=int, default=1000,
                       help='Maximum cycles to run (default: 1000)')
    parser.add_argument('--duration', type=float, default=10.0,
                       help='Mining duration in seconds (default: 10.0)')
    parser.add_argument('--difficulty', type=lambda x: int(x, 0), default=0x000FF,
                       help='Mining difficulty in hex (default: 0x000FF)')
    parser.add_argument('--output', type=str, default='paper_tape.txt',
                       help='Output file for paper tape program')
    
    args = parser.parse_args()
    
    print("="*60)
    print("Ferranti Mark 1 Simulator")
    print("RustChain Proof-of-Antiquity Miner")
    print("="*60)
    print()
    
    # Create computer
    computer = FerrantiMark1()
    
    if args.program:
        # Generate paper tape program
        program = create_miner_program()
        ascii_program = encode_program_ascii(program)
        
        with open(args.output, 'w') as f:
            f.write(ascii_program)
        
        print(f"Paper tape program written to: {args.output}")
        print(f"Program size: {len(program)} words")
        print()
        print("First 10 words (ASCII encoding):")
        for i, word in enumerate(program[:10]):
            print(f"  {i:03X}: {word:05X}")
    
    elif args.mine:
        # Run mining session
        miner = RustChainMiner(computer, difficulty=args.difficulty)
        miner.run_mining_session(duration_seconds=args.duration)
    
    elif args.run:
        # Run simulator
        program = create_miner_program()
        computer.load_program(program)
        
        print(f"Loaded {len(program)} word program")
        print(f"Running for up to {args.cycles} cycles...")
        print()
        
        computer.run(max_cycles=args.cycles)
        
        print()
        print(f"Execution complete:")
        print(f"  Instructions executed: {computer.instruction_count}")
        print(f"  Cycles: {computer.cycle_count}")
        print(f"  Paper tape output: {''.join(computer.paper_tape_output[:50])}")
        print(f"  Hoot sounds: {len(computer.hoot_sounds)}")
    
    elif args.demo:
        # Run demonstration
        print("[DEMO] Running Ferranti Mark 1 Mining Demonstration")
        print()
        
        # Load program
        program = create_miner_program()
        computer.load_program(program)
        
        # Run mining
        miner = RustChainMiner(computer, difficulty=0x00100)
        miner.run_mining_session(duration_seconds=5.0)
        
        # Show fingerprint
        print(f"Hardware Fingerprint: {miner.generate_fingerprint()}")
        print()
        print("[OK] Demonstration complete!")
        print()
        print("This implementation demonstrates:")
        print("  [Y] Ferranti Mark 1 architecture simulation")
        print("  [Y] Williams tube memory with unique patterns")
        print("  [Y] Paper tape I/O simulation")
        print("  [Y] Hoot command audio output")
        print("  [Y] Simplified Proof-of-Antiquity mining")
        print()
        print(f"Bounty Wallet: {miner.wallet}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
