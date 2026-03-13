# IBM 650 RustChain Miner Port - Implementation Plan

## 🎯 Bounty Overview

**Target**: Port RustChain miner to IBM 650 (1953) - First mass-produced computer
**Reward**: 200 RTC (LEGENDARY Tier)
**Wallet**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

---

## 📋 Technical Specifications

### IBM 650 Architecture

| Component | Specification |
|-----------|---------------|
| **Released** | 1953 (announced), 1954 (first installation) |
| **Clock Speed** | 125 kHz |
| **Memory** | Magnetic drum: 1,000 / 2,000 / 4,000 words |
| **Word Size** | 10 bi-quinary coded decimal digits |
| **Architecture** | Two-address, decimal (not binary!) |
| **Technology** | ~2,000 vacuum tubes |
| **Weight** | 5,400-6,263 pounds |
| **Speed** | ~40 instructions/second |
| **Access Time** | 2.5ms average (drum at 12,500 rpm) |
| **Instructions** | 44 basic opcodes (97 with all options) |

### Instruction Format

```
┌─────────────┬───────────────┬───────────────┐
│   Opcode    │  Data Addr    │  Next Addr    │
│   (2 digits)│  (4 digits)   │  (4 digits)   │
└─────────────┴───────────────┴───────────────┘
```

### Addressable Registers

| Address | Register |
|---------|----------|
| 8000 | Console switches |
| 8001 | Distributor |
| 8002 | Lower accumulator |
| 8003 | Upper accumulator |
| 9000-9059 | Core storage (optional IBM 653) |

---

## 🔧 Implementation Challenges

### 1. Network Connectivity ⚠️ CRITICAL

The IBM 650 has **NO built-in networking**. Solutions:

**Approach A: IBM 533 Card Reader Interface** (Recommended)
- Use a modern microcontroller (Arduino Due / Raspberry Pi Pico)
- Simulate punched card input/output
- Microcontroller handles TCP/IP and HTTPS
- IBM 650 reads "network response cards" and punches "request cards"

**Approach B: IBM 727 Magnetic Tape Interface**
- Use tape emulator (e.g., Tape-Flux with modern storage)
- Batch processing: collect attestations, write to tape, process offline

**Approach C: Console Switch Manual Entry**
- For demonstration only
- Operator manually enters data via console switches
- Not practical for mining, but proves concept

### 2. Decimal vs Binary

IBM 650 uses **bi-quinary coded decimal**, not binary:
```
Bi-quinary code: 7 bits per digit
- 2 "bi" bits (0-1, 2-3, 4-5, 6-7, 8-9)
- 5 "quinary" bits (0-4)

Example: 7 = bi(0110000) + quinary(00010) = 0110010
```

**Solution**: Implement decimal arithmetic routines for:
- SHA256 (decimal version - very slow!)
- HTTP request construction
- JSON parsing (manual string building)

### 3. Memory Constraints

Maximum 4,000 words × 10 digits = 40,000 digits ≈ 35 KB

**Memory Layout**:
```
0000-0009   System / I/O buffers
0010-0099   Network interface routines
0100-0199   SHA256 decimal routines
0200-0399   Attestation logic
0400-0999   Data storage
1000-1999   SOAP assembly / optimization
2000-3999   Free / variables
8000-8003   Special registers
9000-9059   Core storage (if IBM 653 installed)
```

### 4. No TLS/HTTPS

**Solution**: RustChain provides HTTP endpoints for vintage hardware:
```
POST http://rustchain.org/vintage/attest
Content-Type: application/x-www-form-urlencoded

miner_id=IBM650-001&arch=ibm650&fingerprint=...
```

---

## 📦 Implementation Phases

### Phase 1: Hardware Setup (50 RTC)

**Goal**: Get IBM 650 communicating with modern network

**Tasks**:
1. [ ] Acquire or access IBM 650 hardware
   - Museums: Computer History Museum, Smithsonian, etc.
   - Private collectors
   - University archives

2. [ ] Build card reader interface
   - Arduino Due (84 MHz, plenty of I/O)
   - Connect to IBM 533 card reader pins
   - Simulate card read/punch signals

3. [ ] Implement card protocol
   - 80 columns per card
   - Numeric data only (base 650)
   - Alphabetic device for characters (optional)

**Deliverables**:
- Photo/video of IBM 650 with interface connected
- Test: Read card from 650, send to serial/USB
- Schematic and source code for interface

---

### Phase 2: SOAP Assembly System (50 RTC)

**Goal**: Create assembler and toolchain

**Tasks**:
1. [ ] Implement SOAP (Symbolic Optimal Assembly Program)
   - Port existing SOAP II code (available in archives)
   - Add modern output formats

2. [ ] Create cross-assembler (modern PC → IBM 650)
   - Python/JavaScript implementation
   - Optimal instruction placement (drum timing)

3. [ ] Build simulator for testing
   - JavaScript/Python IBM 650 emulator
   - Test code before loading to real hardware

**Deliverables**:
- Working SOAP assembler
- Cross-assembler with optimization
- Simulator passing test programs

---

### Phase 3: Core Miner Implementation (75 RTC)

**Goal**: Implement miner on IBM 650

**Tasks**:
1. [ ] Decimal SHA256 implementation
   - Use existing 650 arithmetic routines
   - Optimize for drum access patterns
   - Expect ~30 seconds per hash (brutal but works!)

2. [ ] Hardware fingerprinting
   - Vacuum tube warm-up drift (unique per machine)
   - Drum motor timing variations
   - Console switch contact resistance patterns
   - Card reader mechanical timing

3. [ ] Attestation protocol
   - Build HTTP POST request (as decimal strings)
   - Send via card interface to microcontroller
   - Parse JSON response (manual parsing)

4. [ ] Optimal drum programming
   - Place instructions for minimal access time
   - Use TLU instruction for table lookups
   - Exploit drum band structure (50 words/band)

**Deliverables**:
- Complete miner source code (SOAP assembly)
- Attestation appearing in `rustchain.org/api/miners`
- `device_arch: "ibm650"`, `device_family: "vacuum_tube"`

---

### Phase 4: Proof & Documentation (25 RTC)

**Goal**: Verify and document

**Tasks**:
1. [ ] Video demonstration
   - IBM 650 running miner
   - Card reader punching requests
   - Console lights showing activity

2. [ ] Performance metrics
   - Hashes per hour (expect: ~100-120/hour)
   - Power consumption (~25 kW!)
   - Heat output (vacuum tubes run hot)

3. [ ] Documentation
   - Build instructions
   - Programming guide
   - Historical context

**Deliverables**:
- 10+ minute video of mining operation
- Miner visible in network API
- Complete documentation

---

## 🎁 Antiquity Multiplier

Based on RustChain's multiplier system:

| Hardware | Era | Multiplier |
|----------|-----|------------|
| Modern x86_64 | Current | 1.0× |
| Apple Silicon | 2020+ | 1.2× |
| PowerPC G4 | 1999-2005 | 2.5× |
| Apple II (6502) | 1977 | 4.0× |
| **IBM 650** | **1953** | **5.0× (MAX)** |

**Expected Earnings**:
- Base: 0.12 RTC/epoch
- With 5.0× multiplier: **0.60 RTC/epoch**
- Per day (144 epochs): **86.4 RTC/day**
- Per month: **~2,592 RTC/month**

This would be the **highest-earning single miner** in the RustChain network!

---

## 🛠️ Required Resources

### Hardware
- IBM 650 Console Unit (with drum memory)
- IBM 533 Card Read Punch Unit
- IBM 655 Power Unit
- Arduino Due or similar microcontroller
- Level shifters (650 uses different voltage levels)
- Custom connector for card reader interface

### Software
- SOAP II assembler (archived, needs porting)
- Cross-assembler (modern PC)
- Simulator for testing
- Microcontroller firmware (C/C++)

### Documentation
- IBM 650 Manual of Operation (available on Bitsavers)
- IBM 533 Technical Manual
- SOAP II source code (archived)

---

## 📅 Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | 4-6 weeks | Hardware interface working |
| Phase 2 | 3-4 weeks | Assembler + simulator ready |
| Phase 3 | 6-8 weeks | Miner running on real hardware |
| Phase 4 | 2 weeks | Documentation + verification |
| **Total** | **15-20 weeks** | **Full completion** |

---

## ⚠️ Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|------------|
| No accessible IBM 650 hardware | HIGH | Partner with museums, use emulator for dev |
| Card reader interface too complex | MEDIUM | Use simpler tape or console interface |
| SHA256 too slow to be practical | MEDIUM | Accept slow speed, prove concept works |
| Vacuum tube failures | MEDIUM | Source spare tubes, work with collectors |
| Power consumption (25 kW!) | HIGH | Ensure adequate electrical supply |

---

## 🏆 Unique Value Proposition

This is not just a miner port - it's **computing history meeting blockchain**:

1. **First mass-produced computer** (2,000 units made)
2. **Vacuum tube era** - pre-transistor computing
3. **Donald Knuth's machine** - TAOCP is dedicated to the IBM 650
4. **Decimal architecture** - fundamentally different from all modern computers
5. **Drum memory programming** - a lost art of optimal programming

**Marketing angle**: "The 1953 Computer Mining Crypto in 2026"

---

## 📝 Claim Instructions

Comment on this issue: "I would like to work on this"

**Partial claims accepted** - complete any phase for its RTC amount:
- Phase 1: 50 RTC
- Phase 2: 50 RTC
- Phase 3: 75 RTC
- Phase 4: 25 RTC

**Full completion**: 200 RTC total

**Wallet for bounty**: `RTC4325af95d26d59c3ef025963656d22af638bb96b`

---

## 📚 Resources

- [Bitsavers IBM 650 Documents](http://www.bitsavers.org/pdf/ibm/650/)
- [Columbia University IBM 650 History](http://www.columbia.edu/acis/history/650.html)
- [IBM Archives: 650 Exhibition](https://www.ibm.com/ibm/history/exhibits/650/)
- [SOAP II Source Code](http://www.bitsavers.org/pdf/ibm/650/24-4000-0_SOAPII.pdf)
- [Knuth's IBM 650 Appreciation](http://ed-thelen.org/comp-hist/KnuthIBM650Appreciation.pdf)
- [Dr. Dobb's: The IBM 650](https://www.drdobbs.com/the-ibm-650/184404809)

---

*1953 meets 2026. Vacuum tubes mining cryptocurrency. The ultimate proof that old hardware still has computational value and dignity.*
