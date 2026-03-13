# Ferranti Mark 1 Miner Architecture

## Executive Summary

This document describes the architectural design for porting the RustChain miner to the Ferranti Mark 1 (1951), the world's first commercially available stored-program digital computer.

**Key Challenge**: The Ferranti Mark 1 has approximately **1.25 KB** of total memory and **no networking capabilities**. This implementation is a **conceptual adaptation** that demonstrates the spirit of Proof-of-Antiquity on history's first commercial computer.

---

## 1. Hardware Architecture

### 1.1 Ferranti Mark 1 Specifications

```
┌─────────────────────────────────────────────────────────────────┐
│                    FERRANTI MARK 1 (1951)                        │
├─────────────────────────────────────────────────────────────────┤
│  Main Memory:    8 Williams tubes × 64 words = 512 words        │
│  Word Size:      20 bits (instructions), 40 bits (data)         │
│  Total Memory:   512 × 20 = 10,240 bits ≈ 1.25 KB               │
│                                                                 │
│  Accumulator:    80 bits (A register)                           │
│  MQ Register:    40 bits (multiplicand/quotient)                │
│  B-Lines:        8 index registers (20 bits each)               │
│                                                                 │
│  Secondary:      512-page magnetic drum (30ms revolution)       │
│  I/O:            Paper tape (5-bit Baudot)                      │
│  Instructions:   ~50 operations                                 │
│  Cycle Time:     1.2 milliseconds                               │
│  Multiply:       2.16 milliseconds                              │
│                                                                 │
│  Vacuum Tubes:   4,050                                          │
│  Weight:         10,000 lbs (4.5 tonnes)                        │
│  Power:          ~25 kW                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Memory Organization

```
Williams Tube Memory Layout:
┌────────────────────────────────────────┐
│ Tube 0: Lines 00-3F (Addresses 000-07F)│
│ Tube 1: Lines 00-3F (Addresses 080-0FF)│
│ Tube 2: Lines 00-3F (Addresses 100-17F)│
│ Tube 3: Lines 00-3F (Addresses 180-1FF)│
│ Tube 4: Lines 00-3F (Addresses 200-27F)│
│ Tube 5: Lines 00-3F (Addresses 280-2FF)│
│ Tube 6: Lines 00-3F (Addresses 300-37F)│
│ Tube 7: Lines 00-3F (Addresses 380-3FF)│
└────────────────────────────────────────┘

Address Format (20-bit word):
┌──────┬─────────────────────────────────┐
│ 5 bits │ 15 bits                      │
│ OP   │ ADDRESS                       │
│ 19-15│ 14-0                          │
└──────┴─────────────────────────────────┘
```

### 1.3 Instruction Set (Simplified)

| Opcode | Mnemonic | Description | Cycles |
|--------|----------|-------------|--------|
| 0x00 | STOP | Halt execution | 1 |
| 0x01 | LOAD | Load accumulator from memory | 2 |
| 0x02 | STORE | Store accumulator to memory | 2 |
| 0x03 | ADD | Add memory to accumulator | 2 |
| 0x04 | SUB | Subtract memory from accumulator | 2 |
| 0x05 | MUL | Multiply by memory (80-bit result) | 5 |
| 0x06 | DIV | Divide by memory | 8 |
| 0x07 | JUMP | Unconditional jump | 1 |
| 0x08 | JNEG | Jump if accumulator negative | 1 |
| 0x09 | JZER | Jump if accumulator zero | 1 |
| 0x0A | LOAD_B | Load B-line | 2 |
| 0x0B | ADD_B | Add to B-line | 2 |
| 0x0C | INPUT | Input from paper tape | 10 |
| 0x0D | OUTPUT | Output to paper tape | 10 |
| 0x0E | HOOT | Audio output (pitch from A) | 1 |
| 0x0F | RAND | Random number | 2 |
| 0x10 | AND | Logical AND | 2 |
| 0x11 | OR | Logical OR | 2 |
| 0x12 | NOT | Logical NOT | 2 |

---

## 2. Proof-of-Antiquity Adaptation

### 2.1 Original RustChain PoA

The modern RustChain miner performs:
1. **Hardware Fingerprinting**: CPU, MAC addresses, serial numbers
2. **Attestation**: Submit fingerprint to network
3. **Enrollment**: Register for current epoch
4. **Mining**: Submit shares based on hardware uniqueness
5. **Verification**: Network validates hardware authenticity

### 2.2 Ferranti Mark 1 Adaptation

| Original Component | Ferranti Mark 1 Equivalent |
|-------------------|---------------------------|
| CPU ID | Williams tube residual charge pattern |
| MAC Address | Tube serial number (simulated) |
| Network Attestation | Paper tape output |
| Epoch Enrollment | Drum rotation cycle |
| Share Submission | HOOT command audio proof |
| Hardware Verification | Unique tube fingerprint |

### 2.3 Hardware Fingerprinting

Each Williams tube has a unique "residual charge" pattern that serves as its fingerprint:

```python
class WilliamsTube:
    def __init__(self):
        self.serial_pattern = random.randint(0, 0xFFFFF)
        self.words = [0] * 64
    
    def get_fingerprint(self) -> int:
        # Residual charge pattern is unique to each tube
        return self.serial_pattern

def generate_system_fingerprint(tubes: List[WilliamsTube]) -> str:
    # Combine all tube patterns
    patterns = [tube.get_fingerprint() for tube in tubes]
    combined = sum(patterns) & 0xFFFFFFFFFFFFFFFF
    return f"{combined:016X}"
```

### 2.4 Mining Algorithm

```
┌─────────────────────────────────────────────────────────────┐
│              FERRANTI MARK 1 MINING ALGORITHM                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INITIALIZATION                                           │
│     - Read Williams tube patterns → FINGERPRINT              │
│     - Initialize NONCE = 0                                   │
│     - Load DIFFICULTY threshold                              │
│                                                              │
│  2. MINING LOOP                                              │
│     LOOP:                                                    │
│       a. NONCE ← NONCE + 1                                   │
│       b. HASH ← FINGERPRINT XOR NONCE                        │
│       c. IF HASH < DIFFICULTY THEN                           │
│            - SHARE FOUND!                                    │
│            - OUTPUT "SHARE" to paper tape                    │
│            - HOOT (audio proof)                              │
│            - Record share                                    │
│       d. JUMP LOOP                                           │
│                                                              │
│  3. SHARE SUBMISSION                                         │
│     - Paper tape output serves as "submission"               │
│     - HOOT sound provides audio proof-of-work                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.5 Difficulty Calculation

The difficulty is adjusted based on the Ferranti Mark 1's computational capacity:

```
Base Difficulty: 0x000FF (255 out of 1,048,576 possible values)
Probability: ~0.024% per attempt
Expected Attempts: ~4,096
Expected Time: 4,096 × 1.2ms ≈ 4.9 seconds per share
```

---

## 3. Paper Tape Program

### 3.1 Program Encoding

The Ferranti Mark 1 used a **5-bit Baudot code** with a deliberately obscure character mapping:

```
Binary Value → Character
00000 → /
00001 → E
00010 → @
00011 → A
00100 → :
00101 → S
00110 → I
00111 → U
01000 → ½
01001 → D
01010 → R
01011 → J
01100 → N
01101 → F
01110 → C
01111 → K
10000 → T
10001 → Z
10010 → L
10011 → W
10100 → H
10101 → Y
10110 → P
10111 → Q
11000 → O
11001 → B
11010 → G
11011 → "
11100 → M
11101 → X
11110 → V
11111 → £
```

### 3.2 Program Structure

```
Address  Content   Description
─────────────────────────────────────────────────
000      0x00000   CLEAR accumulator
001      0x28000   LOAD_B B0=0 (initialize nonce)
002      0x78000   RAND (get tube pattern)
003      0x48010   STORE pattern at addr 0x010
004      0x58000   ADD_B B0++ (increment nonce)
005      0x48010   LOAD pattern
006      0x58000   ADD B0 (XOR approximation)
007      0x8800A   JNEG to 0x00A (if hash < 0)
008      0x78004   JUMP to 0x004 (continue loop)
009      0x00000   (unused)
00A      0x68000   OUTPUT (paper tape)
00B      0x70000   HOOT (audio proof)
00C      0x00000   CLEAR
00D      0x78004   JUMP to 0x004
00E      0x00000   STOP
```

### 3.3 Paper Tape Output Example

```
Program (hex):
00000 28000 78000 48010 58000 48010 58000 8800A 78004 00000 68000 70000 00000 78004 00000

Encoded (ASCII):
/E@A :SIU ½DRJ NFCK TZLW HYPQ OBG" MXV£ ...
```

---

## 4. Implementation Details

### 4.1 Simulator Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PYTHON SIMULATOR                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │  WilliamsTube    │    │  MagneticDrum    │               │
│  │  - 64 words      │    │  - 512 pages     │               │
│  │  - serial_pattern│    │  - 30ms rotation │               │
│  └──────────────────┘    └──────────────────┘               │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │ FerrantiMark1   │                             │
│              │ - 8 tubes       │                             │
│              │ - accumulator   │                             │
│              │ - MQ register   │                             │
│              │ - B-lines       │                             │
│              │ - PC            │                             │
│              └────────┬────────┘                             │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │ RustChainMiner  │                             │
│              │ - fingerprint   │                             │
│              │ - difficulty    │                             │
│              │ - shares        │                             │
│              └─────────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Key Classes

#### FerrantiMark1
- `tubes`: List of 8 WilliamsTube instances
- `drum`: MagneticDrum for secondary storage
- `accumulator_high`, `accumulator_low`: 80-bit accumulator
- `mq_register`: 40-bit MQ
- `b_lines`: 8 index registers
- `program_counter`: Current instruction address
- Methods: `load_program()`, `execute_instruction()`, `run()`

#### RustChainMiner
- `computer`: FerrantiMark1 instance
- `difficulty`: Mining difficulty threshold
- `shares_found`: List of valid shares
- `nonce`: Current nonce value
- Methods: `generate_fingerprint()`, `compute_hash()`, `mine_share()`, `submit_share()`

### 4.3 Mining Share Structure

```python
@dataclass
class MiningShare:
    timestamp: int      # Unix timestamp
    fingerprint: str    # 16-character hex hardware fingerprint
    nonce: int          # 20-bit nonce used
    hash_value: int     # Computed hash (must be < difficulty)
    difficulty: int     # Difficulty threshold
    
    def is_valid(self) -> bool:
        return self.hash_value < self.difficulty
```

---

## 5. Performance Analysis

### 5.1 Theoretical Performance

| Metric | Ferranti Mark 1 | Modern CPU |
|--------|-----------------|------------|
| Cycle Time | 1.2 ms | ~0.3 ns |
| Instructions/sec | ~833 | ~3,000,000,000 |
| Memory Access | 2 cycles | ~0.5 cycles |
| Multiplication | 2.16 ms | ~3 cycles |
| Hash Attempts/sec | ~8 | ~1,000,000,000 |

### 5.2 Expected Mining Rate

```
Difficulty 0x000FF:
- Probability per attempt: 255 / 1,048,576 ≈ 0.024%
- Expected attempts per share: 4,096
- Expected time per share: 4,096 × 1.2ms ≈ 4.9 seconds
- Shares per hour: ~735

Difficulty 0x0000F:
- Probability per attempt: 15 / 1,048,576 ≈ 0.0014%
- Expected attempts per share: 69,905
- Expected time per share: 69,905 × 1.2ms ≈ 84 seconds
- Shares per hour: ~43
```

---

## 6. Testing

### 6.1 Unit Tests

```bash
# Run test suite
python test_miner.py

# Test individual components
python -c "from ferranti_simulator import *; c = FerrantiMark1(); print(c.get_fingerprint())"
```

### 6.2 Integration Tests

```bash
# Run mining demonstration
python ferranti_simulator.py --demo

# Run extended mining session
python ferranti_simulator.py --mine --duration 60 --difficulty 0x00100

# Generate paper tape program
python ferranti_simulator.py --program --output my_program.txt
```

### 6.3 Expected Output

```
============================================================
Ferranti Mark 1 Simulator
RustChain Proof-of-Antiquity Miner
============================================================

🔨 Starting RustChain Mining Session on Ferranti Mark 1
Difficulty: 0x00100
Duration:   10.0s
Wallet:     RTC4325af95d26d59c3ef025963656d22af638bb96b
============================================================

[HOOT] ♫ Pitch 173
============================================================
SHARE FOUND!
============================================================
Wallet:     RTC4325af95d26d59c3ef025963656d22af638bb96b
Fingerprint: A3F7B2C1D8E9F0A1
Nonce:      007B3
Hash:       000F7
Difficulty: 00100
Timestamp:  1710334567
============================================================

============================================================
MINING SESSION COMPLETE
============================================================
Duration:     10.23s
Attempts:     1000
Shares Found: 2
Instructions: 8547
Cycles:       8547
============================================================
```

---

## 7. Limitations and Future Work

### 7.1 Current Limitations

1. **No Real Hardware**: This is a simulation; no actual Ferranti Mark 1 exists that can run this code
2. **Simplified Hash**: Uses XOR instead of cryptographic hash (SHA-256 impossible on Ferranti)
3. **No Networking**: Paper tape output simulates network submission
4. **No Persistence**: Shares not persisted to drum storage in current implementation

### 7.2 Potential Enhancements

1. **Drum Storage**: Implement share persistence to magnetic drum
2. **Multi-Tube Mining**: Parallel mining across all 8 Williams tubes
3. **Paper Tape Reader**: Physical paper tape output (with vintage hardware)
4. **Audio Verification**: Record HOOT sounds as proof-of-work
5. **Museum Display**: Run on Ferranti Mark 1 emulator in computer museum

---

## 8. Conclusion

This implementation demonstrates that while the Ferranti Mark 1 cannot run a modern blockchain miner, the **core concepts of Proof-of-Antiquity** can be adapted to any computational substrate, no matter how limited.

The Ferranti Mark 1's unique characteristics—Williams tube memory patterns, paper tape I/O, and the iconic HOOT command—provide a charming analogy to modern hardware fingerprinting and network attestation.

**Bounty Claim**: Wallet `RTC4325af95d26d59c3ef025963656d22af638bb96b`

---

*"The Ferranti Mark 1 played the first computer music in 1951. Now it mines RustChain. Progress!"*
