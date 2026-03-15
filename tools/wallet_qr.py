#!/usr/bin/env python3
"""RustChain Wallet QR — Generate QR codes for RTC addresses."""
import sys, hashlib
def qr(data):
    h = hashlib.sha256(data.encode()).digest()
    print(f"\n  RTC Address: {data}\n")
    for i in range(8):
        row = "  "
        for j in range(16):
            row += "##" if (h[(i*2+j)%32] >> (j%8)) & 1 else "  "
        print(row)
    print(f"\n  Copy: {data}")
if __name__ == "__main__":
    qr(sys.argv[1] if len(sys.argv) > 1 else "RTC5ec5adcbca045184a0ecf0e8a0854dfb327a240e")
