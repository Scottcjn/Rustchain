# RustChain PoA Retro Test Plan

## ✅ Objectives

- Confirm legacy device can submit fingerprint to the PoA API
- Validate REST and raw TCP ingest
- Detect emulators and apply penalties

---

## 🧪 Test Matrix

| Platform | Method | Validator | Expected Result |
|----------|--------|-----------|-----------------|
| DOSBox + NE2000 | poa_dos.c | validate_dos.py | ✅ Accepted (test flag) |
| Real 386 + mTCP | poa_dos.c | validate_dos.py | ✅ Full score |
| Amiga Forever | amiga_fingerprint.asm | validate_amiga.py | 🟥 Emulator penalty |
| Real A500 | amiga_fingerprint.asm | validate_amiga.py | ✅ Full score |
| Raw TCP | netcat or retro socket | poa_tcp_listener.py | ✅ Routed & logged |

---

## 🔎 Validation Checks

- ROM checksum verified?
- AttnFlags zeroed? (bad)
- CPU model known?
- Message + fingerprint present?

---

## 🌐 Forwarding & Logs

Ensure TCP daemon logs all incoming:
```bash
[+] Connection from 192.168.0.42
[✓] Forwarded to REST API
```
