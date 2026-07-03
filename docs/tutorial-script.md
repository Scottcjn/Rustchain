# RustChain Video Tutorial Script

**Title:** Getting Started with RustChain Mining in 10 Minutes
**Target length:** 8-10 minutes
**Audience:** Beginners with basic Linux/command line knowledge

---

## SCENE 1: Introduction (0:00 - 0:45)

**[Screen: RustChain logo animation]**

**Narration:**
> "What if I told you that old computer in your closet — the one from 2005 — could earn you cryptocurrency? Welcome to RustChain, a blockchain that rewards vintage hardware with higher mining multipliers. I'm going to show you how to get started in under 10 minutes."

**[Screen: Side-by-side of a modern gaming PC and an old ThinkPad]**

> "This gaming PC earns 0.8x. This old ThinkPad from 2008 earns 1.0x. And a PowerPC Mac from 2003? That earns 2.5x. The older your hardware, the more you earn."

---

## SCENE 2: What You Need (0:45 - 1:30)

**[Screen: Checklist overlay]**

**Narration:**
> "Here's what you need:"

> "1. An old computer — anything from the last 20 years works. Desktop, laptop, even a Raspberry Pi."

> "2. An operating system — Linux is easiest, but Windows and macOS work too."

> "3. Python 3.6 or newer — we'll install this together."

> "4. An internet connection — Wi-Fi or Ethernet."

> "That's it. No expensive GPU, no special hardware. Let's get started."

---

## SCENE 3: Installing Python (1:30 - 2:30)

**[Screen: Terminal on a Linux desktop]**

**Narration:**
> "First, let's make sure Python is installed. Open a terminal."

**[Type commands]**

```bash
python3 --version
```

> "If you see Python 3.6 or higher, you're good. If not, install it:"

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
```

> "On Windows, download Python from python.org and make sure to check 'Add Python to PATH' during installation."

---

## SCENE 4: Installing the Miner (2:30 - 3:30)

**[Screen: Terminal]**

**Narration:**
> "Now install the RustChain miner with pip:"

```bash
pip3 install clawrtc
```

> "This installs the official RustChain CLI miner. It's lightweight — under 50MB of RAM."

**[Screen: pip install completing]**

> "Done. Let's verify it's installed:"

```bash
clawrtc --version
```

---

## SCENE 5: The Fingerprint Check (3:30 - 4:30)

**[Screen: Terminal]**

**Narration:**
> "Before we start mining, let's run a dry run to see what hardware RustChain detects:"

```bash
clawrtc mine --wallet my-first-miner --dry-run
```

**[Screen: Output showing hardware detection]**

> "Look at this output. It detected our CPU, calculated the multiplier, and verified the fingerprint. This is how RustChain knows you're running on real hardware."

**[Point to specific lines]**

> "See this line: 'CPU architecture detected: Intel Core 2 Duo (1.0x multiplier)'. That's your antiquity bonus. On a Pentium III, this would say 2.0x. On a PowerPC G4, it would say 2.5x."

---

## SCENE 6: Start Mining (4:30 - 5:30)

**[Screen: Terminal]**

**Narration:**
> "Now let's actually start mining:"

```bash
clawrtc mine --wallet my-first-miner
```

> "The miner will ask you to agree to the consent screen. Type YES."

**[Screen: Consent prompt, typing YES]**

> "And we're mining! You can see the attestation being submitted every few seconds."

**[Screen: Mining output flowing]**

> "Each attestation proves to the network that you're running on real vintage hardware. The network verifies your fingerprint and credits your wallet with RTC."

---

## SCENE 7: Checking Your Balance (5:30 - 6:15)

**[Screen: New terminal tab]**

**Narration:**
> "Let's check our balance. Open a new terminal:"

```bash
clawrtc balance --wallet my-first-miner
```

> "Or you can check on the block explorer at rustchain.org/explorer."

**[Screen: Explorer showing wallet]**

> "Paste your wallet address and you'll see your balance, mining history, and hardware multiplier."

---

## SCENE 8: Running at Startup (6:15 - 7:00)

**[Screen: Terminal]**

**Narration:**
> "Want your miner to start automatically when the computer boots? Here's how:"

**Linux (systemd):**

```bash
sudo tee /etc/systemd/system/rustchain-miner.service << 'EOF'
[Unit]
Description=RustChain Miner
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/clawrtc mine --wallet my-first-miner
Restart=always
RestartSec=30
Nice=19
CPUSchedulingPolicy=idle

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable rustchain-miner
sudo systemctl start rustchain-miner
```

**Windows:**
> "Create a batch file and put it in the Startup folder."

**macOS:**
> "Use launchd or just add it to your Login Items."

---

## SCENE 9: Vintage Hardware Bonus (7:00 - 8:00)

**[Screen: Montage of old hardware]**

**Narration:**
> "Here's where it gets exciting. If you have genuinely old hardware — pre-2000 — you can earn significantly more."

**[Screen: Vintage profile list]**

> "RustChain supports over 30 vintage CPU profiles. Intel 386 from 1985? That's a 3.0x multiplier. PowerPC 601 from 1993? 2.5x. Even a Commodore 64's MOS 6502 gets 2.8x."

> "To see all supported profiles:"

```bash
python3 vintage_miner/vintage_miner_client.py --list-profiles
```

> "The older and rarer your hardware, the more you earn. It's like a digital museum that pays you."

---

## SCENE 10: Community and Bounties (8:00 - 9:00)

**[Screen: GitHub issues page]**

**Narration:**
> "RustChain has an active bounty program. You can earn RTC for all kinds of contributions:"

**[Screen: Bounty list overlay]**

> "- 50 RTC for setting up mining on vintage hardware"
> "- 10 RTC for creating a tutorial video like this one"
> "- 5 RTC for writing a blog post"
> "- 3 RTC for sharing on social media"
> "- 2 RTC for registering your Beacon ID"

> "Check the issues page at github.com/Scottcjn/Rustchain for the latest bounties."

---

## SCENE 11: Outro (9:00 - 10:00)

**[Screen: RustChain logo]**

**Narration:**
> "That's it! You're now a RustChain miner. Your old computer is earning RTC, preserving computing history, and reducing e-waste."

> "Here's a quick recap:"

> "1. Install Python"
> "2. Install clawrtc with pip"
> "3. Run the fingerprint check"
> "4. Start mining"
> "5. Check your balance on the explorer"

> "If you found this helpful, star the repo at github.com/Scottcjn/Rustchain and leave a comment on the bounty issue."

> "Happy mining, and may your old hardware earn you more than your new one."

**[Screen: Links to repo, explorer, and Discord]**

---

## PRODUCTION NOTES

### Equipment Needed
- Screen recording software (OBS, QuickTime, or similar)
- Microphone for narration
- Text editor for scripts
- Terminal with RustChain miner installed

### B-Roll Suggestions
- Photos of old hardware (ThinkPad, Power Mac G4, Raspberry Pi)
- Close-ups of CPU chips
- Time-lapse of old computer booting Linux
- Terminal output flowing during mining

### Estimated Recording Time
- Script read-through: 15 minutes
- Screen recording (3 takes): 45 minutes
- Editing and post-production: 2-3 hours
- Total: ~3-4 hours

### Accessibility
- Add captions/subtitles for all narration
- Use high-contrast terminal theme for readability
- Provide transcript in video description
- Include all commands as copyable text in description
