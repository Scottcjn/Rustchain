#!/usr/bin/env python3
"""
Fossil Record Data Generator
============================
Generates attestation history data for the RustChain Fossil Record visualizer.
In production, connects to the RustChain node database to export attestation history.

Usage:
    python generate_fossil_data.py [--epochs 500] [--output data/fossils.json]

The generated data/fossils.json is consumed by site/fossils/index.html.
For production deployment, point --api to your RustChain node:
    python generate_fossil_data.py --api http://localhost:8080 --epochs 500
"""

import argparse
import json
import sys
import hashlib
from datetime import datetime

# Architecture definitions matching index.html
ARCHITECTURES = [
    {'id': '68K',    'name': 'Motorola 68000',       'era': 1, 'color': '#7B3F00', 'first': 'Genesis'},
    {'id': 'G3G4',   'name': 'PowerPC G3/G4',         'era': 2, 'color': '#B87333', 'first': 'Epoch 12'},
    {'id': 'G5',     'name': 'PowerPC G5 (970)',      'era': 3, 'color': '#CD7F32', 'first': 'Epoch 47'},
    {'id': 'SPARC',  'name': 'Sun SPARC',             'era': 4, 'color': '#DC143C', 'first': 'Epoch 83'},
    {'id': 'MIPS',   'name': 'MIPS R-series',         'era': 5, 'color': '#008B8B', 'first': 'Epoch 120'},
    {'id': 'POWER8', 'name': 'IBM POWER8',            'era': 6, 'color': '#1E3A8A', 'first': 'Epoch 195'},
    {'id': 'ARM',    'name': 'ARM v8-A',              'era': 7, 'color': '#9CA3AF', 'first': 'Epoch 260'},
    {'id': 'X86',    'name': 'Modern x86-64',         'era': 8, 'color': '#D1D5DB', 'first': 'Epoch 310'},
]

DEVICE_NAMES = {
    '68K':    ['Macintosh II', 'Amiga 500', 'Atari ST', 'Sharp X68000', 'Mac SE'],
    'G3G4':   ['PowerBook G3', 'iMac G3', 'Blue & White G3', 'Power Mac G4', 'iBook G3'],
    'G5':     ['Power Mac G5', 'iMac G5', 'Xserve G5', 'PowerBook G5', 'Mac Pro G5'],
    'SPARC':  ['UltraSPARC II', 'SunBlade 1000', 'Sun Fire V480', 'SPARCstation 20', 'Blade 2000'],
    'MIPS':   ['SGI Indy', 'DECstation 5000', 'MIPS Magnum', 'Nintendo 64', 'PlayStation 2'],
    'POWER8': ['IBM S812L', 'Talospace S824', 'Raptor Computing', 'OpenPOWER', 'PowerNV'],
    'ARM':    ['Apple M1', 'Raspberry Pi 4', 'Graviton 2', 'Apple M2', 'Apple M3'],
    'X86':    ['AMD EPYC 7763', 'Intel Xeon Gold', 'Core i9-13900K', 'Ryzen 9 7950X', 'EPYC 9654'],
}


def seeded_random(seed: int):
    """Deterministic seeded random for reproducible data."""
    s = seed
    while True:
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        yield (s >> 0) / 4294967296.0


def generate_fossil_data(num_epochs: int, seed: int = 0xDEADBEEF) -> dict:
    """
    Generate fossil attestation data for `num_epochs`.
    In production, replace this with actual RustChain node DB queries.

    Returns a dict with:
      - metadata: { num_epochs, generated_at, source }
      - epochs: list of { epoch, miners: [{archId, minerId, device, fingerprintQuality, rtcEarned}] }
      - summary: per-architecture totals
    """
    rng = seeded_random(seed)

    # Architecture lifecycle (start_epoch, peak_epoch, end_epoch, peak_count)
    lifecycle = {
        '68K':    (0,   50,  180, 8),
        'G3G4':   (12,  120, 280, 45),
        'G5':     (47,  150, 350, 38),
        'SPARC':  (83,  180, 380, 22),
        'MIPS':   (120, 220, 420, 30),
        'POWER8': (195, 300, 480, 55),
        'ARM':    (260, 380, 500, 70),
        'X86':    (310, 450, 500, 120),
    }

    arch_map = {a['id']: a for a in ARCHITECTURES}
    all_miners = []
    epochs_data = []

    for epoch in range(num_epochs):
        epoch_miners = []

        for arch in ARCHITECTURES:
            arch_id = arch['id']
            start, peak, end, peak_count = lifecycle[arch_id]

            if epoch < start or epoch > end:
                continue

            # Bell-curve adoption
            if epoch <= peak:
                progress = (epoch - start) / max(1, peak - start)
                count = int(peak_count * progress * (1 + next(rng) * 0.3))
            else:
                decline = 1 - (epoch - peak) / max(1, end - peak)
                count = int(peak_count * decline * (1 + next(rng) * 0.3))

            count = max(0, min(count, peak_count * 2))

            for m in range(count):
                fpq = int(60 + next(rng) * 40 * (1 - abs(progress - 0.5) if epoch <= peak else abs(decline - 0.5)))
                rtc = int(fpq * (1 + next(rng) * 3) * (arch['era'] * 0.5 + 0.5))
                miner_id = f"{arch_id}-{epoch:04X}-{m:04X}"
                device = DEVICE_NAMES[arch_id][int(next(rng) * len(DEVICE_NAMES[arch_id]))]

                miner = {
                    'archId': arch_id,
                    'archName': arch['name'],
                    'minerId': miner_id,
                    'device': device,
                    'fingerprintQuality': fpq,
                    'rtcEarned': rtc,
                    'epoch': epoch,
                    'appeared': epoch == start,
                }
                epoch_miners.append(miner)
                all_miners.append(miner)

        epochs_data.append({'epoch': epoch, 'miners': epoch_miners})

    # Summary per architecture
    summary = {}
    for arch in ARCHITECTURES:
        arch_miners = [m for m in all_miners if m['archId'] == arch['id']]
        if arch_miners:
            summary[arch['id']] = {
                'name': arch['name'],
                'color': arch['color'],
                'era': arch['era'],
                'totalMiners': len(arch_miners),
                'totalRTC': sum(m['rtcEarned'] for m in arch_miners),
                'avgFingerprintQuality': round(sum(m['fingerprintQuality'] for m in arch_miners) / len(arch_miners), 1),
                'firstAppearance': arch['first'],
            }

    return {
        'metadata': {
            'numEpochs': num_epochs,
            'generatedAt': datetime.utcnow().isoformat() + 'Z',
            'source': 'generate_fossil_data.py (seeded sample — replace with node DB in production)',
            'generator': 'RustChain Fossil Record Generator v1.0',
            'totalMiners': len(all_miners),
            'totalRTC': sum(m['rtcEarned'] for m in all_miners),
        },
        'epochs': epochs_data,
        'summary': summary,
    }


def fetch_from_node(api_url: str, num_epochs: int) -> dict:
    """
    Fetch real attestation data from a running RustChain node.
    Requires the node to have the /api/v1/attestations endpoint.

    In production, uncomment and configure:
    """
    # import requests
    # resp = requests.get(f"{api_url}/api/v1/attestations",
    #                     params={'from_epoch': 0, 'to_epoch': num_epochs}, timeout=30)
    # resp.raise_for_status()
    # return resp.json()
    raise NotImplementedError(
        "Configure your RustChain node API URL and uncomment the requests code above. "
        "Expected endpoint: GET /api/v1/attestations?from_epoch=0&to_epoch=N "
        "returning: [{'epoch': int, 'miners': [{'archId', 'minerId', 'device', 'fingerprintQuality', 'rtcEarned'}]}]"
    )


def main():
    parser = argparse.ArgumentParser(description='Generate RustChain fossil attestation data')
    parser.add_argument('--epochs', type=int, default=500, help='Number of epochs to generate')
    parser.add_argument('--output', default='data/fossils.json', help='Output JSON path')
    parser.add_argument('--api', default=None, help='RustChain node API URL (skip to use sample data)')
    parser.add_argument('--seed', type=int, default=0xDEADBEEF, help='Random seed for sample data')
    args = parser.parse_args()

    if args.api:
        print(f"Fetching from RustChain node: {args.api}")
        data = fetch_from_node(args.api, args.epochs)
    else:
        print(f"Generating sample fossil data for {args.epochs} epochs (seed=0x{args.seed:X})")
        data = generate_fossil_data(args.epochs, args.seed)

    output_path = args.output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    meta = data['metadata']
    print(f"\nGenerated: {output_path}")
    print(f"  Epochs: {meta['numEpochs']}")
    print(f"  Total miners: {meta['totalMiners']:,}")
    print(f"  Total RTC earned: {meta['totalRTC']:,}")
    print(f"\nPer-architecture summary:")
    for arch_id, info in data['summary'].items():
        print(f"  {arch_id:8s}: {info['totalMiners']:5d} miners, {info['totalRTC']:8d} RTC, avg FPQ {info['avgFingerprintQuality']}")


if __name__ == '__main__':
    main()
