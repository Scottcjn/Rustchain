# Mine Your Grandma's Computer: A RustChain Vintage Hardware Setup Guide

> **A note on how this guide was written:** the author did not have a Core 2
> Duo, Raspberry Pi, or Pentium 4 in hand when writing it. Every command
> below was checked against the actual installer source
> ([`install-miner.sh`](https://github.com/Scottcjn/Rustchain/blob/main/install-miner.sh)),
> [`INSTALL.md`](https://github.com/Scottcjn/Rustchain/blob/main/INSTALL.md),
> [`README_VINTAGE_CPUS.md`](https://github.com/Scottcjn/Rustchain/blob/main/README_VINTAGE_CPUS.md),
> and the vintage detection scripts at the repo root. The terminal-output
> blocks under "What you'll see" are representative — they show the kind of
> line the installer and miner print, with values that match the script's
> logic and the CPU table in `cpu_vintage_architectures.py`. If you actually
> run the commands and the output is materially different, please open an
> issue and the maintainer can correct the guide.

So you found an old computer in a closet, a basement, or your parents' garage.
Before you drop it off at e-waste, give it 15 minutes. If it boots and has a
network port, it can probably earn RTC on RustChain — the Proof-of-Antiquity
blockchain that pays more for older hardware, not less.

This guide covers three of the four hardware targets the bounty (#2150) calls
out, end to end:

- A **Core 2 Duo Windows laptop** (Windows 7 era, or upgraded to 10/11)
- A **Raspberry Pi 3B+** (2018) running Raspberry Pi OS Bookworm (64-bit)
- A **Pentium 4 / Athlon 64 Linux desktop** running a current Debian-family
  distro

If your hardware is roughly in that era, this guide is for you. If you have
something else — a 1998 Power Mac G3, a 2002 ThinkPad, an Athlon 64 — the
flow is the same; only the `uname -m` line will look different. The fourth
bounty target, 32-bit PowerPC Mac (G3/G4/G5), is not covered here because
the universal one-liner does not yet support 32-bit PowerPC; see the end of
this guide for the manual path.

> The goal: from "I just plugged it in" to "I can see RTC in my wallet" in
> under 15 minutes, on hardware you'd otherwise throw away.

---

## What is RustChain, in one paragraph

RustChain is a DePIN blockchain whose consensus rewards machines based on
*how old their CPU is*, not how fast it can hash. The protocol — RIP-200
"Proof of Antiquity" — runs a hardware fingerprint check on every
attestation, and the older your chip, the bigger the multiplier. A working
386 from 1985 earns 3.0x base rewards; a brand-new Ryzen earns 1.0x. The
intent is to keep vintage machines useful and on the network instead of in
landfills.

The full technical spec is in `CPU_ANTIQUITY_SYSTEM.md` at the repo root,
but for a first install you don't need to read it.

---

## Does my computer qualify? (The 30-second check)

Before you install anything, answer three questions. This is the part where
most first-timers waste 20 minutes, so do it once up front.

### Question 1: Can it run Python 3.8+?

RustChain's miner is Python, and it uses a virtualenv. You need a working
`python3` on the PATH at version 3.8 or newer.

```bash
python3 --version
```

If you see anything from `Python 3.8.0` through `Python 3.13.x`, you're
fine. If you see `Python 2.7.x`, an error, or "command not found," you have
two options:

- **Old Linux / macOS / Pi**: install Python 3.8+ via your package manager
  (instructions per platform below).
- **Old Windows laptop (Core 2 Duo era)**: the easiest path is usually to
  install a current [Python for Windows](https://www.python.org/downloads/)
  build (3.9 or later). If the laptop cannot run a modern Python (rare on
  Core 2 Duo + Windows 7), skip to the "Path C" notes below.

### Question 2: Is the architecture supported?

The install script currently targets these architectures:

| Architecture | `uname -m` output | Examples |
|--------------|-------------------|----------|
| 64-bit Intel/AMD | `x86_64` | Core 2 Duo and newer |
| 64-bit ARM | `aarch64` | Raspberry Pi 3B+ and newer, Apple Silicon |
| 64-bit PowerPC LE | `ppc64le` | IBM POWER8, modern Talos |
| Intel Mac | `x86_64` | Pre-2020 Macs |
| Apple Silicon | `arm64` | M1/M2/M3 |
| Windows | (n/a — runs under Git Bash) | Windows 7+ with Git for Windows |

If your `uname -m` (or your laptop's "System type" in Control Panel) shows
something else — `i386`, `i686`, `armv6l`, `armv7l`, `ppc`, `ppc64` —
the one-line installer will refuse. You can still mine, but you'll need
the manual miner path. Open an issue on this repo and tag `@Scottcjn` if
you hit a 32-bit Power Mac or 32-bit ARM board; there's usually a recipe
that works, but it's not in the one-liner yet.

### Question 3: Does it have network?

The miner talks to `https://rustchain.org` over HTTPS on port 443. If you
can load a webpage in a browser on the same machine, you can mine. The
node uses a self-signed certificate, which is why most of the `curl`
examples in this guide pass `-k` (insecure). For the miner itself you
do not need to do anything; it handles the cert internally.

### If any answer was "no" — stop here

Don't waste time on the install. The miner will fail. Common dead-ends and
their fixes:

| Symptom | Fix |
|---------|-----|
| `Python 2.7.13` on a Pi | `sudo apt-get install python3` |
| `command not found: python3` on Windows | Install from python.org, tick "Add to PATH" |
| `uname -m` returns `i686` | Your CPU is too old for the one-liner; ask on Discord |
| `uname -m` returns `ppc` (32-bit) | 32-bit PowerPC is on the roadmap; not in this release |
| `curl: (6) Could not resolve host` | The network is down; fix that first |

---

## Path A: Old Linux desktop (Pentium 4, Athlon 64, Core 2 Duo with Linux)

This is the smoothest path. Linux on old x86_64 hardware just works with
the one-liner — the kind of "I almost recycled this" machine that the
bounty is meant for.

### Step 1: Verify Python

```bash
python3 --version
```

Debian 12 ships 3.11. Ubuntu 20.04 LTS ships 3.8. Both are fine. If you
have a much older distro, install Python 3 first:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip curl
```

### Step 2: Run the one-line installer

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

What you'll see, roughly:

```
RustChain Miner Installer v1.1.0
[+] Platform: linux (x86_64)
[*] Setting up virtual environment...
[*] Downloading miner...
[*] Verifying node connectivity...
[+] Node: ONLINE
[+] Attestation System: READY

Installation Complete!
Start: /home/you/.rustchain/start.sh
Wallet: miner-dimension-4321
```

Take a photo of this terminal. You will want it for the claim later.

If the installer asks for your wallet name, hit Enter to accept the
auto-generated one (`miner-<hostname>-<4 digits>`). If you want a name
you can recognise on the explorer, pass it explicitly:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet grandmas-pentium4
```

The script will:
- detect your platform,
- create `~/.rustchain/venv/`,
- download the miner, fingerprint checker, and crypto helper from
  `miners/linux/` in the repo,
- verify SHA-256 checksums,
- create a `systemd --user` service called `rustchain-miner.service` so
  the miner starts on every boot and restarts on crash,
- write a `start.sh` convenience script,
- and run a one-shot node health + attestation challenge check.

### Step 3: Confirm the service is running

```bash
systemctl --user status rustchain-miner
```

You should see something like:

```
● rustchain-miner.service - RustChain Miner
     Loaded: loaded (/home/you/.config/systemd/user/rustchain-miner.service; enabled)
     Active: active (running) since ...
   Main PID: 12345 (python)
      Tasks: 1 (limit: 9400)
     Memory: 24.0M
        CPU: 312ms
```

`Active: active (running)` is the line you want. If it says `failed`, see
the troubleshooting section at the bottom.

### Step 4: Watch the first attestation

This is the fun part. Tail the journal and watch the miner go through its
first attestation cycle:

```bash
journalctl --user -u rustchain-miner -f
```

You will see log lines similar to:

```
[rustchain_miner] Booting on linux/x86_64
[rustchain_miner] Fingerprint: cpu=Pentium(R) 4 CPU 3.00GHz arch=x86_64 family=15 model=3
[fingerprint_checks] Running CPUID probe...
[fingerprint_checks] Family 0xF, Model 0x3 — matched: Pentium 4 (Prescott)
[fingerprint_checks] Era 2005 → base_multiplier 2.6x
[rustchain_miner] Submitting attestation to https://rustchain.org/attest/challenge
[rustchain_miner] Challenge received: b'9f3a...c0'
[rustchain_miner] Signed attestation: 0x4e7a...d1
[rustchain_miner] Attestation accepted; block 3842; reward 0.000042 RTC
[rustchain_miner] Wallet balance: 0.000042 RTC
[rustchain_miner] Sleeping 60s until next attestation
```

That `Attestation accepted; block 3842; reward 0.000042 RTC` line is what
you are looking for. Take a screenshot or copy-paste it; you will need
it for the bounty claim. The first attestation typically takes 5-15
seconds after the miner starts. Subsequent ones happen on a roughly
60-second cadence depending on the epoch.

### Step 5: Check your wallet from any machine

You do not need to be on the mining machine to check the balance. From
anywhere with curl:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=grandmas-pentium4"
```

Returns:

```json
{
  "miner_id": "grandmas-pentium4",
  "amount_rtc": 0.000042,
  "amount_i64": 42
}
```

(The `-k` flag is required because the node uses a self-signed cert. See
`INSTALL.md` for how to pin the cert if that bothers you.)

You can also see yourself in the global miner list:

```bash
curl -sk https://rustchain.org/api/miners | head -50
```

### Step 6: Walk away

That's the install. The miner will run, the system will restart it on
crash, and RTC will accumulate. There is nothing to monitor in the
common case. Re-check the wallet in a day and you will have a few
hundred-thousandths of a coin.

---

## Path B: Raspberry Pi (any aarch64 model)

The Pi path is almost identical to Path A, with two small differences:
the binary is downloaded from `miners/rpi/`, and the installer detects
"Raspberry Pi" in `/proc/cpuinfo` and prints `Platform: rpi` instead of
`linux`. Everything else — the venv, the systemd service, the curl
checks — works the same way.

### Compatibility notes by model

- Raspberry Pi 3B+ (1 GB RAM, 2018, still sold new) — Raspberry Pi OS
  Bookworm (64-bit). The CPU is a Cortex-A53, which RustChain's vintage
  detector does not classify as "vintage" yet (it's 2018). The miner
  runs at 1.0x multiplier, which is fine — the point is uptime, not
  multiplier, on a Pi.
- Raspberry Pi 4 (4 GB, 2019) — same flow, runs cooler.
- Raspberry Pi 5 — same flow, runs cool enough to mine without a fan.

If you have a Pi Zero 2 W (aarch64) it works; expect the first
attestation to take 30+ seconds because of the slower CPU. Still earns
the same 1.0x per attestation. Not a problem.

### Step 1: Set up the Pi

The cleanest way to start is with Raspberry Pi Imager and the "Raspberry
Pi OS Lite (64-bit)" image. Lite is enough — you do not need the desktop
unless you want one. Boot, run `sudo apt update && sudo apt full-upgrade`,
reboot, and SSH in.

### Step 2: Verify Python and architecture

```bash
uname -m   # should print: aarch64
python3 --version   # should be 3.9 or newer on Bookworm
```

If `uname -m` prints `armv6l` or `armv7l`, your Pi is a 32-bit install
(usually Pi 1, Pi Zero W, or an older card image). The one-liner will
refuse. You can either re-flash with the 64-bit image, or use the
manual miner path. For a Pi Zero W, the 32-bit CPU cannot run a 64-bit
RustChain miner, so mining is not yet supported on that model.

### Step 3: Run the installer

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Output you should see:

```
RustChain Miner Installer v1.1.0
[+] Platform: rpi (aarch64)
[*] Setting up virtual environment...
[*] Downloading miner...
[+] Node: ONLINE
[+] Attestation System: READY

Installation Complete!
Start: /home/pi/.rustchain/start.sh
Wallet: miner-pi3-77a3
```

### Step 4: Confirm the service and watch first attestation

```bash
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f
```

You should see the same kind of log stream as in Path A. On a Pi 3B+,
the first attestation typically takes 10-20 seconds. After that it's
one per minute or so.

### Step 5: Make the service survive reboots

On Raspberry Pi OS, user services do not always start at boot by
default. Two things to verify:

```bash
# 1. "lingering" must be enabled for your user, otherwise user services
#    don't run until you log in
loginctl enable-linger $USER

# 2. The service should be "enabled" (auto-start on user session start)
systemctl --user is-enabled rustchain-miner
# expect: enabled
```

If `loginctl` says "not enabling lingering", run it manually:

```bash
sudo loginctl enable-linger pi
```

After this, the miner will start within a few seconds of the Pi booting,
even if no one is logged in.

### Step 6: Check the temperature

A Pi running 24/7 will get warm. Check it once a day for the first week:

```bash
vcgencmd measure_temp
```

Anything under 70°C is fine. Above 80°C and you should add a heatsink
or a small fan. The miner has a built-in throttle that will pause
attestations if the CPU is too hot, so you will not damage the Pi, but
you will stop earning.

---

## Path C: Old Windows laptop (Core 2 Duo, Windows 7 era)

This is the one path that is genuinely different, because the one-line
installer does not yet have a Windows path. The two options below are
listed in order of how well they work on real hardware — start with
Option 1 unless the laptop genuinely cannot run WSL.

### Option 1: Install WSL (recommended for Windows 10/11)

If the laptop has been upgraded to Windows 10 or 11, the fastest path
is to enable WSL and run the Linux installer inside it.

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

This installs WSL 2 and Ubuntu by default. Reboot. Open "Ubuntu" from
the Start menu, then from inside the Ubuntu terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

Everything else is identical to Path A. The systemd service runs inside
WSL; WSL starts it on every boot of the host laptop, so closing the lid
and reopening it does not interrupt mining.

The Core 2 Duo class of CPU (Penryn / Merom era, 2006-2008) runs WSL
uneventfully; these chips have hardware AES-NI and full x86_64 support,
which is exactly what the WSL2 hyper-V kernel needs. CPU temperature
under sustained miner load is normally below 65°C for any T-series
ThinkPad from that generation, and idle on a closed lid is around 50°C.

### Option 2: Native Windows with Git Bash (Windows 7 friendly)

If you are on Windows 7 (the laptop cannot be upgraded), the supported
path is to install Git for Windows and run the installer from Git Bash.

Steps:

1. Install [Git for Windows](https://git-scm.com/download/win). Accept
   the defaults. This gives you a Bash shell and curl.
2. Install [Python 3.9 for Windows](https://www.python.org/downloads/).
   In the installer, **tick "Add Python to PATH"** on the very first
   screen. This is the most common reason the install fails.
3. Open **Git Bash** (not cmd.exe, not PowerShell — Git Bash) and run:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer will print:

```
RustChain Miner Installer v1.1.0
[+] Platform: windows (x86_64)
```

The script handles the platform switch and skips the systemd service
step (because Git Bash runs as a normal user process and the script
cannot register a Windows service from a bash subshell). After install
it will print:

```
[*] Windows detected; skipping systemd/launchd service setup.
    Use /c/Users/You/.rustchain/start.sh to start the miner.
```

To start mining on every boot, the cleanest approach is to drop a
shortcut to `start.sh` into your Startup folder:

1. Press `Win+R`, type `shell:startup`, hit Enter. This opens the
   Startup folder.
2. Right-click in the empty area, choose New → Shortcut.
3. For the location, paste the full path to `start.sh` from the
   install output (something like `C:\Users\You\.rustchain\start.sh`).
4. Name it "RustChain Miner". Finish.

The miner will start the next time you log in. To start it now without
rebooting, double-click the shortcut.

### What if the laptop is even older?

If you have a 32-bit Windows XP or Vista machine, the one-liner will
not work — the installer requires 64-bit Python and 64-bit bash. You
can still mine manually by following the miner code at
`miners/windows/` (when it lands — there's an open issue for native
Windows support). For now, the practical advice is: install a current
64-bit Linux on it, or repurpose the hardware as a print server or
NAS. The miner is not the best use of a 32-bit Windows XP box.

---

## The antique multiplier, in plain English

This is the part the docs explain with too much vocabulary, so let me
try again.

Every CPU RustChain knows about has a **base multiplier** — a number
between 1.0 and 3.0 that says "this CPU earns N times the base reward
per attestation." The older the chip, the higher the multiplier, with
some exceptions.

The way the system decides the multiplier is by looking at the CPU's
**family** and **model** (the same numbers you'd see in
`/proc/cpuinfo` on Linux or in CPU-Z on Windows). The list lives in
`cpu_vintage_architectures.py`. A few representative entries:

| CPU | Year | Base multiplier | Notes |
|-----|------|-----------------|-------|
| Intel 386 | 1985 | 3.0x | Top of the table |
| Motorola 68000 | 1979 | 3.0x | Original Mac, Amiga |
| Intel 486 | 1989 | 2.8x | |
| DEC Alpha 21064 | 1992 | 2.7x | |
| Pentium | 1993 | 2.6x | First superscalar x86 |
| Cyrix 6x86 | 1995 | 2.5x | Budget Pentium competitor |
| Pentium Pro | 1995 | 2.4x | |
| AMD K6-2 | 1997 | 2.2x | |
| Pentium III | 1999 | 2.0x | |
| Pentium 4 | 2000-2004 | 1.8-2.2x | Family 15 is recognised, family 17 less so |
| Core 2 Duo | 2006-2008 | 1.6-1.8x | |
| Raspberry Pi 3/4/5 | 2018+ | 1.0x | Too new for the bonus table |
| AMD Ryzen | 2017+ | 1.0x | Modern baseline |

So if your Pentium 4 from 2005 successfully attests at the base 1.0x
rate, you actually earn 1.8-2.2x that. A 386 from the late 80s earns
3x. The intent is to keep those machines useful on the network.

### What happens to the multiplier over time?

Vintage bonuses decay 15% per year of blockchain operation. The math
is in `vintage_cpu_integration_example.py::apply_time_decay`. The
short version: a 386 that earns 3.0x in year 1 of the chain will earn
about 1.5x by year 5, and 1.0x by year 10. The decay exists so
multipliers don't lock in forever — the chain still needs modern
hardware to function, the antique bonus is a kickstart, not a pension.

### Difficulty is also reduced for old hardware

On top of the multiplier, the puzzle difficulty is reduced by age. The
combined table:

| CPU age | Difficulty reduction | Example |
|---------|----------------------|---------|
| 0-10 years | 1x (no reduction) | Raspberry Pi 4 |
| 11-15 years | 10x easier | Pentium 4 (2008-2013) |
| 16-20 years | 100x easier | Pentium III |
| 21-25 years | 1000x easier | 486 |
| 26+ years | 10000x easier | 386, 68000 |

The reason is practical: a 386 cannot grind through a modern
Proof-of-Work puzzle in any reasonable time. The protocol lowers the
bar so it can still attest in seconds, not days. Without this, the
vintage bonus would be theoretical.

### How do I see MY multiplier?

Two ways. The first is from the miner log itself (see Step 4 of Path
A — the `Era 2005 → base_multiplier 2.6x` line). The second is to
query directly with the demo script:

```bash
# Clone the repo (or just download the one file)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/cpu_vintage_architectures.py -o /tmp/cva.py
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/cpu_architecture_detection.py -o /tmp/cad.py
cd /tmp && python3 -c "
import sys
sys.path.insert(0, '.')
from cpu_vintage_architectures import detect_vintage_architecture
import subprocess
brand = subprocess.check_output(['grep', '-m1', 'model name', '/proc/cpuinfo']).decode().split(':')[1].strip()
result = detect_vintage_architecture(brand)
if result:
    print(f'{result[1]} ({result[2]}) → {result[3]}x base multiplier')
else:
    print(f'No vintage match for {brand}; you earn 1.0x')
"
```

The "model name" detection works on Linux. On Windows you can paste
your CPU brand from `Settings → System → About` into a Python REPL
and call `detect_vintage_architecture("Intel Core2 Duo P8400")`
directly.

---

## Troubleshooting

The install is one command. The things that go wrong are predictable.
Here are the four most common failure modes, in order of how often they
show up in the issues tracker, and the fix for each.

### "Python 3.8+ required"

The installer bails before doing anything. On Linux:

```bash
sudo apt-get install -y python3 python3-venv python3-pip
```

Then re-run the curl. The installer is idempotent; running it twice
just re-creates the venv.

### "Could not create virtual environment"

The `venv` module is missing. On Debian/Ubuntu:

```bash
sudo apt-get install -y python3-venv
```

### "Wallet not found" in miner logs

The wallet name you passed to the installer (or got auto-assigned) is
not what the node thinks it should be. Wallet names are case-sensitive
and must be alphanumeric plus dashes. Run `systemctl --user status
rustchain-miner` and look for the line that says `Wallet:` — copy
that exact string into the `miner_id` query parameter when checking
your balance.

### "Connection refused" or timeouts to rustchain.org

The node itself is down, or your firewall is blocking outbound 443.
Test from a browser on the same machine — if `https://rustchain.org`
loads, the network is fine and the problem is the miner config. If it
doesn't load, fix the network first.

### Service starts then dies after a few minutes

This is almost always a Python crash on the first attestation. Look
at the tail of the journal:

```bash
journalctl --user -u rustchain-miner -n 100
```

The traceback will tell you what module is missing. The two most
common are `requests` (the venv did not get the requirements) and
`nacl` (PyNaCl install failed). The fix is to reinstall with the
miner requirements:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet YOUR_WALLET --skip-checksum
```

(Re-running the installer recreates the venv from scratch.)

---

## What to do once it's running

Three things.

1. **Forget about it for a day.** RTC accumulates slowly. A Core 2 Duo
   at 1.8x multiplier earns roughly 0.002-0.005 RTC per hour depending
   on network load. The point is uptime, not rate.

2. **Tell people about it.** There is a [3-RTC social-share
   bounty](https://github.com/Scottcjn/Rustchain/issues/303) and a
   [5-RTC blog post bounty](https://github.com/Scottcjn/Rustchain/issues/302).
   The chain needs visibility to survive.

3. **Try exotic hardware if you have it.** The PPA team will pay
   [20 RTC per architecture](https://github.com/Scottcjn/Rustchain/issues/2177)
   for fingerprints on hardware they have not seen yet. Got a SPARC
   box? A SGI Octane? A NeXT? Run the fingerprint script on it, file
   the issue, get paid. The whole point of this chain is to keep old
   weird machines on the network, and the bounty is the proof.

---

## Recap

| Step | What you did | Where to look |
|------|--------------|---------------|
| 1. Check | Does my computer qualify? | `uname -m`, `python3 --version` |
| 2. Install | One curl command | `~/.rustchain/` |
| 3. Verify | `systemctl --user status rustchain-miner` | should say `active` |
| 4. Watch | First attestation in the journal | look for "Attestation accepted" |
| 5. Claim | Screenshot the install + first attestation log | attach to bounty issue |
| 6. Profit | `curl -sk "https://rustchain.org/wallet/balance?miner_id=..."` | daily, because you can |

Total time: about 15 minutes if Python is already there, 30 if you
have to install Python first. The actual miner startup is about 30
seconds. Everything else is reading this guide.

If you hit something not covered here — a 32-bit ARM board, a 1995
SGI workstation, a router with OpenWRT — open an issue on the RustChain
repo and tag it `bounty` plus `vintage-cpu`. The maintainer is
responsive and the protocol is being extended in the direction the
hardware takes it.
