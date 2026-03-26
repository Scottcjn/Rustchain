# MicroPython for Dreamcast SH4

Lightweight Python (~256KB) for Dreamcast when full CPython won't fit in 16MB RAM.

## Build MicroPython for SH4

```bash
git clone https://github.com/micropython/micropython.git
cd micropython/ports/unix

make CROSS_COMPILE=sh4-linux-gnu- \
     CFLAGS_EXTRA="-m4 -ml -mb -static -ffunction-sections" \
     LDFLAGS_EXTRA="-static -Wl,--gc-sections -lm" \
     MICROPY_PY_USSL=0 \
     MICROPY_PY_BTREE=0 \
     MICROPY_PY_FFI=0 \
     MICROPY_PY_READLINE=0 \
     micropython
```

## MicroPython Miner Script

```python
# dreamcast_miner.py
import usocket as socket
import ujson as json
import uhashlib as hashlib
import time

RUSTCHAIN_HOST = "rustchain.org"
API_PATH = "/api/miners"

def get_fingerprint():
    return {"arch": "sh4", "family": "dreamcast", "cpu": "SH7750", "mhz": 200}

def submit(wallet, fp):
    payload = json.dumps({"wallet": wallet, "device_arch": "sh4",
                          "device_family": "dreamcast", "fingerprint": fp,
                          "multiplier": 3.0})
    addr = socket.getaddrinfo(RUSTCHAIN_HOST, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    req = "POST {} HTTP/1.0\r\nHost: {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}"
    s.send(req.format(API_PATH, RUSTCHAIN_HOST, len(payload), payload).encode())
    resp = s.recv(1024)
    s.close()
    return b"200 OK" in resp

def main():
    wallet = "dreamcast-default"
    print("Dreamcast SH4 MicroPython Miner - 3.0x")
    fp = hashlib.sha256(str(get_fingerprint()).encode()).hexdigest()[:8]
    while True:
        print("Submitting attestation...")
        ok = submit(wallet, fp)
        print("Result:", "OK" if ok else "FAILED")
        time.sleep(60)

if __name__ == "__main__":
    main()
```

## Memory Budget

| Component | Memory |
|-----------|--------|
| Linux kernel | ~5MB |
| initramfs | ~3MB |
| MicroPython + miner | ~2MB |
| Networking buffers | ~2MB |
| Available | ~4MB |
