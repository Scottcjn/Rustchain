# RustChain Miner Client — OpenBSD Port

Honest, secure Proof-of-Antiquity miner client for **OpenBSD** (amd64, sparc64, arm64, i386).

---

## 🛡️ Verify Before Trust (Audit & Safety First)

Verify the exact behavior and payloads of the miner before running or provisioning services:

### 1. Dry Run (No Network Packets Sent)
```bash
python3 miners/openbsd/rustchain_openbsd_miner.py --dry-run --wallet <YOUR_RTC_WALLET>
```

### 2. Inspect Exact Attestation Payload
```bash
python3 miners/openbsd/rustchain_openbsd_miner.py --show-payload
```

### 3. Run Hardware Diagnostic & Integrity Test
```bash
python3 miners/openbsd/rustchain_openbsd_miner.py --test-only
```

---

## 🚀 Installation & Build Recipe

### Step 1: Install OpenBSD Dependencies
Log in as `root` (or use `doas`):
```bash
pkg_add python3 py3-requests
```

### Step 2: Deploy Miner Client
```bash
mkdir -p /usr/local/share/rustchain /var/log/rustchain
useradd -s /sbin/nologin -d /var/empty _rustchain

cp miners/openbsd/rustchain_openbsd_miner.py /usr/local/share/rustchain/
chmod +x /usr/local/share/rustchain/rustchain_openbsd_miner.py
chown -R _rustchain:_rustchain /usr/local/share/rustchain /var/log/rustchain
```

---

## ⚙️ Persistence & Service Management (`rc.d`)

Deploy the native OpenBSD `rc.d` daemon:

```bash
cp miners/openbsd/rc.d/rustchain_miner /etc/rc.d/
chmod 555 /etc/rc.d/rustchain_miner

# Enable in rc.conf.local
rcctl enable rustchain_miner
rcctl set rustchain_miner flags "--wallet <YOUR_RTC_WALLET> --node https://50.28.86.131"

# Start the service
rcctl start rustchain_miner
```

### Service Controls:
- **Check Status**: `rcctl check rustchain_miner`
- **Restart**: `rcctl restart rustchain_miner`
- **Stop**: `rcctl stop rustchain_miner`

---

## 🔍 Honest Attestation Evidence

The OpenBSD port probes hardware via `sysctl` kernel variables (`hw.model`, `hw.ncpu`, `hw.physmem`, `hw.machine`). 
- **Zero Fingerprint Fabrication**: Clock drift and instruction jitter are measured through real microarchitectural loop cycles.
- **Genuine Device Classification**: SPARC/UltraSPARC machines on OpenBSD/sparc64 are classified as `sparc` with full multiplier integrity.
