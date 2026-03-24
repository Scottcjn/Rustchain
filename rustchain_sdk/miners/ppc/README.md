# RustChain PowerPC Miners

Native C miners for PowerPC Macs with hardware entropy collection.

## G4 (2.5x Antiquity Multiplier)
- `rustchain_miner_v6.c` - Latest C miner for G4 with entropy attestation
- `rustchain_miner_g4` - Pre-compiled binary for Mac OS X Tiger (10.4)

### Build on G4:
```bash
gcc -O3 -mcpu=G4 -maltivec -o rustchain_miner rustchain_miner_v6.c -lcurl
```

## G5 (2.0x Antiquity Multiplier)
- `grok_miner_g5.c` - G5-optimized miner
- `entropy_collector.c` - Hardware entropy collection (AltiVec)
- `altivec_quantum_server.c` - AltiVec-optimized entropy server

### Build on G5:
```bash
gcc -O3 -mcpu=G5 -maltivec -o rustchain_miner grok_miner_g5.c -lcurl
```

## Features
- Native PowerPC AltiVec/VMX SIMD
- Hardware entropy from oscillator drift
- Serial number binding for anti-spoof
- Works on Mac OS X 10.4+ (Tiger)
