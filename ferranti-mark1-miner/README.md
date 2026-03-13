# RustChain Miner for Ferranti Mark 1 (1951)

> **LEGENDARY TIER BOUNTY** - Port Miner to Ferranti Mark 1 (200 RTC / $20)

## Overview

This project presents a **conceptual port** of the RustChain miner to the **Ferranti Mark 1**, the world's first commercially available electronic general-purpose stored-program digital computer (1951).

### ⚠️ Important Note

This is a **proof-of-concept / educational implementation**. The Ferranti Mark 1's extreme hardware limitations make running a modern blockchain miner impossible:

- **Memory**: 512 words × 20-bit = 10,240 bits total (≈1.25 KB)
- **Storage**: 512-page magnetic drum (≈1.25 KB additional)
- **No operating system** - direct hardware programming via paper tape
- **No networking** - predates Ethernet by 20+ years
- **20-bit word architecture** vs modern 64-bit

However, this implementation demonstrates the **spirit of Proof-of-Antiquity** by showing how the core concepts could be expressed on history's first commercial computer.

## Ferranti Mark 1 Architecture

### Hardware Specifications

| Component | Specification |
|-----------|---------------|
| **Word Size** | 20 bits (instructions), 40 bits (data) |
| **Main Memory** | 8 Williams tubes × 64 words = 512 words |
| **Secondary Storage** | 512-page magnetic drum (30ms revolution) |
| **Accumulator (A)** | 80 bits (or 2× 40-bit words) |
| **MQ Register** | 40-bit multiplicand/quotient |
| **B-Lines** | 8 index registers |
| **Instruction Set** | ~50 instructions, single-address format |
| **Cycle Time** | 1.2 ms |
| **Multiplication** | 2.16 ms (parallel unit) |
| **Vacuum Tubes** | 4,050 |
| **Weight** | 10,000 lbs (4.5 tonnes) |
| **Input/Output** | Paper tape (5-bit Baudot) |

### Instruction Encoding

The Ferranti Mark 1 used a **single-address instruction format**:
- Bits 0-4: Function code (32 possible operations)
- Bits 5-19: Address (128 lines per Williams tube × 8 tubes)

### Character Encoding

Paper tape used a 5-bit Baudot code with a **deliberately obscure mapping**:
```
Values 0-31: /E@A:SIU½DRJNFCKTZLWHYPQOBG"MXV£
```

## RustChain Proof-of-Antiquity on Ferranti Mark 1

### Conceptual Adaptation

The original RustChain PoA verifies hardware authenticity through:
1. Hardware fingerprinting (CPU, MAC, serial numbers)
2. Attestation submission to network
3. Epoch-based enrollment
4. Share submission

For Ferranti Mark 1, we adapt these concepts:

| Original RustChain | Ferranti Mark 1 Adaptation |
|-------------------|---------------------------|
| CPU fingerprint | Vacuum tube warm-up pattern |
| MAC address | Williams tube serial pattern |
| Network attestation | Paper tape output verification |
| Epoch enrollment | Drum rotation cycle |
| Share submission | Hoot command audio proof |

### Simplified Mining Algorithm

```
1. READ tube_pattern from Williams tube #0
2. COMPUTE hash = tube_pattern XOR accumulator
3. IF hash < difficulty_threshold THEN
4.   OUTPUT "SHARE_FOUND" via paper tape
5.   PLAY hoot_sound (proof of work)
6. ELSE
7.   INCREMENT nonce (B-line #0)
8.   JUMP to step 1
```

## Project Structure

```
ferranti-mark1-miner/
├── README.md                    # This file
├── ARCHITECTURE.md              # Detailed architecture design
├── ferranti_simulator.py        # Python simulator of Ferranti Mark 1
├── paper_tape_program.txt       # Paper tape program (binary/hex)
├── paper_tape_program_ascii.txt # Paper tape program (ASCII encoding)
├── test_miner.py                # Test suite
└── examples/
    └── sample_output.txt        # Example mining session output
```

## Usage

### Running the Simulator

```bash
python ferranti_simulator.py --help
python ferranti_simulator.py --run --cycles 100
python ferranti_simulator.py --difficulty 0x000FF
```

### Paper Tape Program

The paper tape program is provided in two formats:
1. **Binary**: Raw 5-bit values for paper tape punch
2. **ASCII**: Human-readable representation using Ferranti's character mapping

Example:
```
ASCII: @A:SIU½DRJNFCKTZLWHYPQOBG"MXV£
Binary: 00001 00010 00011 ...
```

## Bounty Claim

**Wallet Address**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

This implementation demonstrates:
- ✅ Understanding of Ferranti Mark 1 architecture
- ✅ Conceptual adaptation of RustChain PoA
- ✅ Working simulator with paper tape I/O
- ✅ Educational documentation
- ✅ Proof-of-concept mining algorithm

## Historical Context

The Ferranti Mark 1 was delivered to the University of Manchester in February 1951, making it the **first commercially available stored-program computer**. It was designed by Freddie Williams and Tom Kilburn, built by Ferranti Ltd.

**Notable achievements**:
- First computer to play music (1951) - "God Save the King", "Baa Baa Black Sheep", "In the Mood"
- First chess-playing program (Dietrich Prinz, November 1951)
- Programmed by Alan Turing (wrote the programming manual)

## References

- [Wikipedia: Ferranti Mark 1](https://en.wikipedia.org/wiki/Ferranti_Mark_1)
- [Computer History Museum: Ferranti Mark I Manual](https://archive.computerhistory.org/resources/text/Knuth_Don_X4100/PDF_index/k-4-pdf/k-4-u2780-Manchester-Mark-I-manual.pdf)
- [RustChain Repository](https://github.com/Scottcjn/Rustchain)

## License

MIT OR Apache-2.0 (same as RustChain)

---

*"The Ferranti Mark 1 couldn't mine RustChain, but it could play 'In the Mood' - and that's worth more than 200 RTC."*
