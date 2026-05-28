# Panduan Setup Miner RustChain

Siapkan miner RustChain di hardware Anda dan mulai mendapatkan RTC melalui
atestasi **Proof-of-Antiquity**. Hardware lama mendapat multiplier lebih tinggi:
PowerPC G4 mendapat 2.5×, sedangkan x86_64 modern mendapat 1.0×.

**Node default:**
- `https://rustchain.org`

Node publik disajikan lewat HTTPS. Script miner saat ini memakai
`https://rustchain.org` sebagai default; ubah URL node hanya jika Anda memang
sedang menguji deployment lain.

---

## Multiplier Antiquity (Referensi Cepat)

| Hardware | Multiplier |
|----------|------------|
| PowerPC G4 (sebelum 2003) | 2.5× |
| PowerPC G5 (2003-2006) | 2.0× |
| Apple Silicon (M1/M2) | 1.2× |
| x86_64 modern (setelah 2015) | 1.0× |
| ARM64 Linux (mis. Pi 4) | 1.3× |
| POWER8 (IBM) | 1.8× |

---

## Preflight Cepat Sebelum Mining

Jika belum siap menjalankan loop mining, jalankan dry-run terlebih dahulu. Ini
adalah pemeriksaan kompatibilitas paling aman karena menampilkan deteksi
hardware, status fingerprint, dan kesehatan node tanpa mendaftarkan miner atau
memulai mining.

Entrypoint dry-run saat ini adalah script miner Linux:

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv
source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --dry-run --show-payload
```

Contoh output tingkat tinggi yang diharapkan:

```text
[FINGERPRINT] Running 6 hardware fingerprint checks...
OVERALL RESULT: ALL CHECKS PASSED
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Node URL: https://rustchain.org
[DRY-RUN] CPU: Apple M3
[DRY-RUN] Cores: 8
[DRY-RUN] Memory(GB): 16
[DRY-RUN] Fingerprint pass status: True
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop
```

CPU, jumlah core, memori, dan hasil fingerprint akan berbeda di tiap mesin.
Jika pemeriksaan fingerprint gagal, output itu tetap berguna: sertakan output
dry-run lengkap saat membuka issue atau mengklaim bounty laporan hardware.

---

## Setup Platform

### macOS (Apple Silicon & Intel)

#### Prasyarat

- macOS 10.15 Catalina atau lebih baru
- Xcode Command Line Tools
- Python 3.8+

```bash
# Install Xcode CLI tools (lewati jika sudah terpasang)
xcode-select --install

# Verifikasi versi Python
python3 --version   # harus 3.8+
```

Jika Python lebih lama dari 3.8, install melalui Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

#### Install & Konfigurasi

```bash
# 1. Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/macos

# 2. Buat virtual environment lokal
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependency runtime yang dipakai miner
pip install requests
```

#### Jalankan

```bash
source .venv/bin/activate
python3 rustchain_mac_miner_v2.5.py \
    --miner-id your_wallet_nameRTC \
    --node https://rustchain.org
```

> **Apple Silicon:** Profil fingerprint `arm64` diterapkan otomatis.
> Multiplier Anda adalah 1.2×. Tidak perlu langkah tambahan.
>
> **Catatan dry-run:** Dalam checkout saat ini, entrypoint miner macOS menerima
> `--miner-id`, `--wallet`, dan `--node`, tetapi belum menerima `--dry-run`.
> Gunakan preflight dry-run Linux di atas jika Anda hanya membutuhkan laporan
> kompatibilitas tanpa mining.

---

### Linux - x86_64

#### Prasyarat

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Fedora / RHEL / CentOS
sudo dnf install -y python3 python3-pip git

# Arch
sudo pacman -S python python-pip git
```

Verifikasi Python >= 3.8:

```bash
python3 --version
```

#### Install & Konfigurasi

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Jalankan dry-run terlebih dahulu:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
```

Mulai miner hanya setelah output dry-run terlihat benar:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

#### Jalankan sebagai service systemd

```bash
sudo tee /etc/systemd/system/rustchain-miner.service > /dev/null <<EOF
[Unit]
Description=RustChain Miner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$PWD/.venv/bin/python3 rustchain_linux_miner.py \
    --wallet your_wallet_nameRTC
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-miner
sudo journalctl -u rustchain-miner -f
```

---

### Linux - ARM64 (server ARM 64-bit, instance cloud)

Setup sama seperti Linux x86_64 di atas. Profil fingerprint `arm64_linux`
dimuat otomatis. Tidak perlu paket tambahan.

Pastikan profil yang benar terdeteksi saat startup:

```text
[INFO] Hardware profile: arm64_linux (multiplier=1.3×)
```

---

### Windows (WSL - Windows Subsystem for Linux)

#### Prasyarat

1. Install WSL2 dari PowerShell (Administrator):

```powershell
wsl --install
# Restart saat diminta, lalu buka Ubuntu dari Start menu
```

2. Di dalam WSL Ubuntu:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

#### Install & Konfigurasi

Langkah di dalam WSL sama seperti Linux x86_64:

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

> **Catatan:** Fingerprint hardware WSL diklasifikasikan sebagai `modern_x86`
> (multiplier 1.0×). Windows bare-metal belum didukung; WSL adalah jalur yang
> direkomendasikan.

---

### IBM POWER8

Mesin POWER8 (mis. Talos II, Blackbird, server OpenPOWER) mendapat multiplier
antiquity 1.8×.

#### Prasyarat

```bash
# Fedora / CentOS Stream (ppc64le)
sudo dnf install -y python3 python3-pip git

# Ubuntu ppc64el
sudo apt install -y python3 python3-pip python3-venv git
```

Verifikasi: `python3 --version` (harus >= 3.8)

#### Install & Konfigurasi

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Jalankan:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
```

Saat startup, Anda seharusnya melihat:

```text
[INFO] Hardware profile: ppc64le / POWER8 (multiplier=1.8×)
```

> **SMT:** POWER8 memiliki 8 thread per core. Fingerprint memakai baseline
> single-thread agar perbandingan adil. Tidak perlu tuning SMT.

---

### Raspberry Pi (Pi 3B+, Pi 4, Pi 5)

Raspberry Pi menjalankan ARM Linux dan mendapat multiplier 1.3×.

#### Prasyarat (Raspberry Pi OS / DietPi / Ubuntu ARM)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

Pi 3B+ memakai Python 3.7 secara default pada image lama. Upgrade jika perlu:

```bash
sudo apt install -y python3.9 python3.9-venv
python3.9 -m venv venv
```

#### Install & Konfigurasi

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Jalankan:

```bash
python3 rustchain_linux_miner.py --wallet mypiRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet mypiRTC
```

> **Pi Zero / Pi 2:** Perangkat ini memakai CPU ARMv6/ARMv7. Gunakan
> `python3.9` atau lebih baru. Miner Linux saat ini menentukan profil hardware
> dari probe sistem lokal, jadi tidak ada flag CLI `--arch` manual di
> dokumentasi.

---

## Output Atestasi Berhasil

Jika semuanya berjalan benar, Anda akan melihat output seperti ini:

```text
======================================================================
RustChain Local Linux Miner
RIP-PoA Hardware Fingerprint + Serial Binding v2.0
======================================================================
Node: https://rustchain.org
Wallet: your_wallet_nameRTC

[FINGERPRINT] Running 6 hardware fingerprint checks...
[1/6] Clock-Skew & Oscillator Drift...
  Result: PASS
[2/6] Cache Timing Fingerprint...
  Result: PASS
[3/6] SIMD Unit Identity...
  Result: PASS
[4/6] Thermal Drift Entropy...
  Result: PASS
[5/6] Instruction Path Jitter...
  Result: PASS
[6/6] Anti-Emulation Checks...
  Result: PASS

OVERALL RESULT: ALL CHECKS PASSED
[FINGERPRINT] All checks PASSED - eligible for full rewards
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
```

---

## Masalah Umum & Perbaikan

### Error `VM_DETECTED`

```json
{"error": "VM_DETECTED", "failed_checks": ["thermal_entropy", "clock_skew"]}
```

**Penyebab:** Anda menjalankan miner di dalam virtual machine (VirtualBox,
VMware, WSL 1, Docker, dan sejenisnya).
**Perbaikan:** Jalankan di bare metal. WSL2 lolos pada kernel Windows modern
(>= 19041). WSL1 tidak lolos.

---

### `ModuleNotFoundError: No module named 'nacl'`

```text
ModuleNotFoundError: No module named 'nacl'
```

**Perbaikan:**

Entrypoint miner Linux dan macOS saat ini hanya membutuhkan `requests` untuk
jalur miner dasar. Jika Anda menjalankan script atestasi lama yang mengimpor
`nacl`, install PyNaCl di virtual environment yang sama:

```bash
pip install PyNaCl
```

---

### `Connection refused` / `Failed to connect`

```text
ConnectionRefusedError: [Errno 111] Connection refused
```

**Penyebab:** `NODE_URL` salah atau node sedang down.
**Perbaikan:**

```bash
# Uji konektivitas
curl -fsS https://rustchain.org/health
```

Jika Anda memang menguji node privat, berikan URL dengan `--node`.

---

### Error `HARDWARE_ALREADY_BOUND`

```json
{"error": "HARDWARE_ALREADY_BOUND", "existing_miner": "other_walletRTC"}
```

**Penyebab:** Fingerprint hardware Anda sebelumnya sudah terdaftar ke
`miner_id` lain.
**Perbaikan:** Gunakan `MINER_ID` yang sama seperti pendaftaran awal, atau
hubungi Discord komunitas untuk meminta rebind.

---

### Python 3.7 atau lebih lama terdeteksi

```text
RuntimeError: Python 3.8+ required
```

**Perbaikan:** Install Python 3.9+ melalui package manager atau pyenv:

```bash
# pyenv (cross-platform)
curl https://pyenv.run | bash
pyenv install 3.11.8
pyenv global 3.11.8
```

---

### Atestasi berhasil tetapi tidak ada reward di akhir epoch

**Penyebab:** Miner didaftarkan setelah batas pendaftaran epoch.
**Perbaikan:** Atestasi harus dilakukan sebelum slot 140 pada epoch tersebut
(144 slot per epoch). Pantau endpoint `/epoch` dan pastikan Anda melakukan
atestasi di awal epoch.

```bash
curl -fsS https://rustchain.org/epoch | python3 -m json.tool
```

Jika `slot` > 140, tunggu epoch berikutnya sebelum mengharapkan reward.

---

*Panduan mencakup RustChain v2.2.1-rip200. Node default: https://rustchain.org*
