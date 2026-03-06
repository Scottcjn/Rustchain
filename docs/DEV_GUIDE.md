# RustChain PoA Developer Guide (Retro Edition)

Welcome to the RustChain Proof-of-Antiquity system — a blockchain layer that accepts and preserves computational history. This guide helps you connect legacy hardware to the chain.

## 🔥 Retro PoA Integration

### Supported Devices:
- ✅ Amiga 500 (via Devpac + bsdsocket.library)
- ✅ DOS/FREEDOS machines (via WATTCP)
- ✅ Vintage machines with any TCP/IP stack

## 🧠 What To Send

Your device should send a simple JSON POST or TCP payload to:

```
POST http://<validator-ip>:5000/validate
```

Example JSON:
```json
{
  "device": "Amiga 500",
  "rom": "Kickstart 1.3",
  "fingerprint": "base64-sha256",
  "message": "disk clicked once"
}
```

---

## 🧩 Submitting from DOS

- Use `poa_dos.c` with WATTCP (Turbo C / DJGPP / Watcom)
- Requires NE2000 + packet driver or DOSBox with networking

## 🧩 Submitting from Amiga

- Use `amiga_fingerprint.asm` in Devpac
- Use `bsdsocket.library` to POST over TCP or write `fingerprint.txt` and submit

---

## 🔌 TCP Broadcast Option

Use `poa_tcp_listener.py` to listen for raw JSON TCP connections on port `8585`.

Run with:
```bash
python poa_tcp_listener.py
```

This daemon forwards incoming JSON to your REST API.

