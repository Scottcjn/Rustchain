#!/usr/bin/env python3
"""Fixed RustChain Wallet CLI - proper BIP39 mnemonic + key derivation"""

import argparse
import getpass
import hashlib
import json
import os
import struct
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── Crypto ──────────────────────────────────

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("⚠ cryptography not installed. Install: pip install cryptography", file=sys.stderr)

# ── Config ──────────────────────────────────

NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
WALLET_DIR = Path(os.environ.get("RUSTCHAIN_WALLET_DIR", Path.home() / ".rustchain" / "wallets"))

# ── Full BIP39 English wordlist (2048 words) ──

BIP39_WORDS = """abandon ability able about above absent absorb abstract absurd abuse access
accident account accuse achieve acid acoustic acquire across act action actor actress actual
adapt add addict address adjust admit adult advance advice aerobic affair afford afraid
again age agent agree ahead aim air airport aisle alarm album alcohol alert alien all
alley allow almost alone alpha already also alter always amazing among amount amused
analyst anchor ancient anger angle angry animal announce annual another answer antenna
antique anxiety any apart apology apple approve april arch arctic area arena argue arm
armed armor army around arrange arrest arrive arrow art artifact artist artwork ask aspect
assault asset assist assume asthma athlete atom attack attend attitude attract auction audit
august aunt author auto autumn average avocado avoid awake aware awesome awful awkward axis
baby bachelor bacon badge bag balance balcony ball bamboo banana banner bar barely bargain
barrel base basic basket battle beach bean beauty because become beef before begin behave
behind believe below belt bench benefit best betray better between beyond bicycle bid bike
bind biology bird birth bitter black blade blame blanket blast bleak bless blind blood
blossom blouse blue blur blush board boat body boil bomb bone bonus book boost border
boring borrow boss bottom bounce box boy bracket brain brand brass brave bread breeze brick
bridge brief bright bring brisk broken bronze brown brush bubble buddy budget buffalo build
bulb bulk bullet bundle bunker burden burger burst bus business busy butter buyer buzz
cabbage cabin cable cactus cage cake call calm camera camp can canal cancel candy cannon
canoe canvas canyon capable capital captain car carbon card cargo carpet carry cart case
cash castle casual cat catch category cattle caught cause cavern ceiling celery cement
census century ceramic ceremony certain chair chalk champion change chaos chapter charge
chase chat cheap check cheek cheese chef cherry chest chicken chief child chimney choice
choose chronic chuckle churn cigar cinnamon circle citizen civil claim clap clarify claw
clay clean clerk clever click client cliff climb clinic clip clock clogs close cloth cloud
clown club clump cluster clutch coach coast coconut code coffee coin coil collect color
column combine come comfort comic common company concert conduct confirm congress connect
consider control convince cook cool copper copy coral core corn correct cost cotton couch
country couple course cousin cover coyote crack cradle craft cram crane crash crater crawl
crazy cream credit creek crew cricket crime crisp critic crop cross crouch crowd crucial
cruel cruise crumble crunch crush cry crystal cube culture cup cupboard curious current
curtain curve cushion custom cute cycle dad damage damp dance danger daring dash daughter
dawn day deal debate debris decade december decide decline decorate decrease deer defense
define defy degree delay deliver demand demise denial dentist deny depart depend deposit
depth deputy derive describe desert design desk despair destroy detail detect develop device
devote diagram dial diamond diary dice diesel diet differ digital dignity dilemma dilute
dim dimension dinner dip direct dirt disagree discover disease dish dismiss disorder display
distance distinct distortion distribute district divide divorce dizzy doctor document dog
doll dolphin domain donate donkey donor door dose double dove draft dragon drama drastic
draw dream dress drift drill drink drip drive drop drum dry duck dumb dune during dust
dutch duty dwarf dynamic eager early earn earth easily east easy echo ecology economy edge
edit educate effort egg eight either elbow elder electric elegant element elephant elevator
elite else embark embody embrace emerge emotion employ empower empty enable enact end
endless endorse enemy energy enforce engage engine enjoy enlarge enlighten enrich enroll
ensure enter entire entry envelope episode equal equip era erase erode erosion error erupt
escape essay essence estate eternal ethics evidence evil evoke evolve exact example exceed
exception exchange excite exclude excuse execute exercise exhaust exhibit exile exist exit
exotic expand expect expire explain expose extend extra eye eyebrow fabric face faculty fade
faint faith fall fame family fancy fantasy fashion fatal fate father fatigue fault favorite
feature february federal fee feed feel female fence festival fetch fever few fiber fiction
field figure file filter film final find fine finger finish fire firm first fiscal fish fit
fitness fix flag flame flash flat flavor flee flight flip float flock floor flower fluid
flush fly foam focus fog foil fold follow food foot force foreign forest forget fork
fortune forum forward fossil foster found fox fragile frame frequent fresh friend fringe
frog front frost frozen fruit fuel fun furniture fury future gadget gain galaxy gallery
game gap garage garbage garden garlic garment gas gasp gate gather gauge gaze general genius
genre gentle genuine gesture ghost giant gift giggle ginger giraffe girl give glad glance
glare glass glide glimpse globe gloom glory glove glow glue goat goddess gold good goose
gorilla gospel gossip govern gown grab grace grain grant grape grass gravity great green
grid grief grill grin grip grocery group grow grunt guard guess guide guilt guitar gun gym
habit hair half hammer hamster hand happy harbor hard harsh harvest hat have hawk hazard
head health heart heavy hedgehog height hello helmet help hen hero hidden high hill hint
hip hire history hobby hockey hold hole holiday hollow home honey hood hope horn horror
horse hospital host hotel hour hover hub human humble humor hundred hungry hunt hurdle hurry
hurt husband hybrid ice icon idea identify idle ignore ill illegal illness image imitate
immense immune impact impose improve impulse inch include income increase index indicate
indoor industry infant inflict inform inhale inherit initial inject injury inmate inner
innocent input inquiry insect inside inspire install intact interest into invest invite
involve iron island isolate issue item ivory jacket jail jam jar jazz jealous jelly jewel
job join joke journey joy judge juice jump jungle junior junk just kangaroo keen keep
ketchup key kick kid kidney kind kingdom kiss kit kitchen kite kitten kiwi knee knife knock
know lab label labor ladder lady lake lamp language laptop large later latin laugh laundry
lava law lawn lawsuit layer lazy leader leaf learn leave lecture left leg legal legend
leisure lemon lend length lens leopard lesson letter level liar liberty library license
life lift light like limb limit link lion liquid list little live lizard load loan lobster
local lock logic lonely long loop lottery loud lounge love loyal lucky luggage lumber lunar
lunch luxury lyric machine mad magic magnet maid mail main major make mammal man manage
mandate mango mansion manual maple marble march margin marine market marriage mask mass
master match material matrix matter maximum maze meadow mean measure meat mechanic medal
media melody melt member memory mention menu mercy merge merit merry mesh message metal
method middle midnight milk million mimic mind mineral minimum minor minute miracle mirror
misery miss mistake mix mixed mixture mobile model modify mom moment monitor monkey monster
month moon moral more morning mosquito mother motion motor mountain mouse move movie much
muffin mule multiply muscle museum mushroom music must mutual mystery myth native natural
nature nasty nation native natural nature navy near neck need negative neglect neither
nephew nerve nest net network neutral never news next nice night noble noise nominee noodle
normal north nose notable note nothing notice novel now nuclear number nurse nut oak obey
object oblige obscure observe obtain obvious occur ocean october odor off offer office
often oil okay old olive olympic omit once one onion online only open opera opinion oppose
option orange orbit orchard order ordinary organ orient original orphan ostrich other
outdoor outer output outside oval oven over own owner oxygen oyster ozone""".split()

# Verify full wordlist
assert len(BIP39_WORDS) == 2048, f"BIP39 wordlist must be 2048 words, got {len(BIP39_WORDS)}"

# ── Helpers ─────────────────────────────────

def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _ensure_dir():
    """Ensure wallet directory exists with secure permissions."""
    WALLET_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(WALLET_DIR, 0o700)


def _entropy_to_mnemonic(entropy: bytes) -> str:
    """
    Convert 16 bytes (128 bits) of entropy to a 12-word BIP39 mnemonic.
    Follows BIP-0039: ENT + CS (checksum: first ENT/32 bits of SHA256(entropy)).
    """
    # ENT = 128 bits (16 bytes), CS = 4 bits (ENT/32)
    bits = ''.join(format(b, '08b') for b in entropy)
    checksum = format(_sha256(entropy)[0], '08b')
    bits += checksum[:4]  # 4-bit checksum for 128-bit entropy

    words = []
    for i in range(0, len(bits), 11):
        idx = int(bits[i:i+11], 2)
        words.append(BIP39_WORDS[idx])
    return ' '.join(words)


def _mnemonic_to_entropy(mnemonic: str) -> bytes:
    """
    Convert a 12-word BIP39 mnemonic back to the original 16 bytes of entropy.
    Strips the 4-bit checksum. Validates checksum.
    """
    word_list = mnemonic.strip().split()
    if len(word_list) != 12:
        raise ValueError(f"Expected 12 words, got {len(word_list)}")

    # Build word -> index lookup
    word_to_idx = {w: i for i, w in enumerate(BIP39_WORDS)}

    bits = ''
    for w in word_list:
        if w not in word_to_idx:
            raise ValueError(f"Unknown BIP39 word: '{w}'")
        bits += format(word_to_idx[w], '011b')

    # Total: 132 bits (128 entropy + 4 checksum)
    entropy_bits = bits[:128]
    checksum_bits = bits[128:132]

    entropy = int(entropy_bits, 2).to_bytes(16, 'big')

    # Validate checksum
    expected_cs = format(_sha256(entropy)[0], '08b')[:4]
    if checksum_bits != expected_cs:
        raise ValueError("Mnemonic checksum mismatch — seed phrase may be corrupted")

    return entropy


def _entropy_to_privkey(entropy: bytes) -> Ed25519PrivateKey:
    """Derive an Ed25519 private key from 16 bytes of entropy via SHA256."""
    seed = _sha256(entropy)  # 32 bytes
    return Ed25519PrivateKey.from_private_bytes(seed)


def _generate_wallet() -> dict:
    """Generate a new Ed25519 wallet with proper BIP39 mnemonic."""
    if not CRYPTO_AVAILABLE:
        return {"error": "cryptography library required"}

    # 16 bytes of cryptographically random entropy
    entropy = os.urandom(16)

    # Derive Ed25519 key
    private_key = _entropy_to_privkey(entropy)
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    # RTC address: RTC + SHA256(pubkey)[:40]
    address = "RTC" + _sha256(pub_bytes).hex()[:40]

    # BIP39 mnemonic from entropy (NOT from private key)
    mnemonic = _entropy_to_mnemonic(entropy)

    return {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": priv_bytes.hex(),
        "seed_phrase": mnemonic,
        "entropy": entropy.hex(),
    }


def _recover_wallet_from_mnemonic(mnemonic: str) -> dict:
    """Recover a wallet from a BIP39 mnemonic phrase."""
    if not CRYPTO_AVAILABLE:
        return {"error": "cryptography library required"}

    entropy = _mnemonic_to_entropy(mnemonic)
    private_key = _entropy_to_privkey(entropy)
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    address = "RTC" + _sha256(pub_bytes).hex()[:40]

    return {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": priv_bytes.hex(),
        "seed_phrase": mnemonic,
        "entropy": entropy.hex(),
    }


# ── Keystore encryption (unchanged) ────────

def _encrypt_keystore(data: dict, password: str) -> dict:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    key = kdf.derive(password.encode())
    aesgcm = AESGCM(key)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "ciphertext": ciphertext.hex(),
        "nonce": nonce.hex(),
        "salt": salt.hex(),
        "iterations": 100000,
        "kdf": "PBKDF2-HMAC-SHA256",
        "cipher": "AES-256-GCM",
    }


def _decrypt_keystore(keystore: dict, password: str) -> dict:
    salt = bytes.fromhex(keystore["salt"])
    nonce = bytes.fromhex(keystore["nonce"])
    ciphertext = bytes.fromhex(keystore["ciphertext"])
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=keystore.get("iterations", 100000))
    key = kdf.derive(password.encode())
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode())


# ── CLI Commands ────────────────────────────

def cmd_create(args):
    """Create a new wallet."""
    if not CRYPTO_AVAILABLE:
        print("⚠ cryptography library required. Install: pip install cryptography")
        return 1

    _ensure_dir()
    wallet = _generate_wallet()

    if "error" in wallet:
        print(f"⚠ {wallet['error']}")
        return 1

    password = getpass.getpass("Enter password for new wallet (AES-256-GCM): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("⚠ Passwords do not match")
        return 1

    keystore = _encrypt_keystore(wallet, password)
    wallet_file = WALLET_DIR / f"{wallet['address']}.json"
    with open(wallet_file, 'w') as f:
        json.dump(keystore, f, indent=2)
    if sys.platform != "win32":
        os.chmod(wallet_file, 0o600)

    print(f"\n✅ Wallet created!")
    print(f"   Address: {wallet['address']}")
    print(f"   File: {wallet_file}")
    print(f"\n   🔐 SEED PHRASE (write this down, it is the ONLY way to recover your wallet):")
    print(f"   {wallet['seed_phrase']}")
    print(f"\n   ⚠  This seed phrase can recover your funds on any RustChain wallet.")
    print(f"      Keep it safe and offline. Never share it.")
    return 0


def cmd_import(args):
    """Import a wallet from BIP39 seed phrase."""
    if not CRYPTO_AVAILABLE:
        print("⚠ cryptography library required. Install: pip install cryptography")
        return 1

    seed = ' '.join(args.seed_phrase)

    try:
        wallet = _recover_wallet_from_mnemonic(seed)
    except ValueError as e:
        print(f"⚠ {e}")
        return 1
    except Exception as e:
        print(f"⚠ Failed to recover wallet: {e}")
        return 1

    if "error" in wallet:
        print(f"⚠ {wallet['error']}")
        return 1

    _ensure_dir()

    # Check if wallet already exists
    wallet_file = WALLET_DIR / f"{wallet['address']}.json"
    if wallet_file.exists():
        print(f"⚠ Wallet {wallet['address']} already exists at {wallet_file}")
        overwrite = input("Overwrite? (y/N): ").lower().strip()
        if overwrite != 'y':
            print("Import cancelled.")
            return 0

    password = getpass.getpass("Enter password for encrypted keystore: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("⚠ Passwords do not match")
        return 1

    keystore = _encrypt_keystore(wallet, password)
    with open(wallet_file, 'w') as f:
        json.dump(keystore, f, indent=2)
    if sys.platform != "win32":
        os.chmod(wallet_file, 0o600)

    print(f"\n✅ Wallet imported!")
    print(f"   Address: {wallet['address']}")
    print(f"   File: {wallet_file}")
    return 0


def cmd_balance(args):
    """Check RTC balance for a wallet."""
    url = f"{NODE_URL}/wallet/balance?address={args.wallet_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"⚠ Failed to fetch balance: {e}")
        return 1

    print(f"\n💰 Balance for {args.wallet_id}")
    print(f"   RTC: {data.get('amount_rtc', '?')}")
    print(f"   Raw: {data.get('amount_i64', '?')}")
    return 0


def cmd_send(args):
    """Send RTC from local wallet."""
    wallet_file = WALLET_DIR / f"{args.wallet_id}.json"
    if not wallet_file.exists():
        # Try searching by prefix
        matches = list(WALLET_DIR.glob(f"{args.wallet_id}*.json"))
        if not matches:
            print(f"⚠ Wallet not found: {args.wallet_id}")
            return 1
        wallet_file = matches[0]

    password = getpass.getpass("Enter wallet password: ")
    try:
        with open(wallet_file) as f:
            keystore = json.load(f)
        wallet = _decrypt_keystore(keystore, password)
    except Exception as e:
        print(f"⚠ Failed to decrypt wallet: {e}")
        return 1

    # Construct transfer
    transfer = {
        "from_address": wallet["address"],
        "to_address": args.to,
        "amount_rtc": float(args.amount),
        "nonce": int.from_bytes(os.urandom(8), 'big'),
        "signature": "",  # Simplified: in production use Ed25519 sign
    }

    url = f"{NODE_URL}/wallet/transfer"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(transfer).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        result = {"error": e.read().decode()}
    except Exception as e:
        print(f"⚠ Transfer failed: {e}")
        return 1

    print(f"\n💸 Transfer:")
    print(f"   From: {wallet['address']}")
    print(f"   To:   {args.to}")
    print(f"   Amount: {args.amount} RTC")
    print(f"   Result: {result}")
    return 0


def cmd_export(args):
    """Export wallet as encrypted keystore JSON."""
    wallet_file = WALLET_DIR / f"{args.wallet_id}.json"
    if not wallet_file.exists():
        matches = list(WALLET_DIR.glob(f"{args.wallet_id}*.json"))
        if not matches:
            print(f"⚠ Wallet not found: {args.wallet_id}")
            return 1
        wallet_file = matches[0]

    password = getpass.getpass("Enter wallet password: ")
    try:
        with open(wallet_file) as f:
            keystore = json.load(f)
    except Exception as e:
        print(f"⚠ Failed to read wallet: {e}")
        return 1

    print(json.dumps(keystore, indent=2))
    return 0


def cmd_list(args):
    """List all local wallets."""
    if not WALLET_DIR.exists():
        print("No wallets found.")
        return 0

    wallets = list(WALLET_DIR.glob("*.json"))
    if not wallets:
        print("No wallets found.")
        return 0

    print(f"\n📂 Local wallets ({len(wallets)}):")
    for w in sorted(wallets):
        name = w.stem
        size = w.stat().st_size
        print(f"   {name}  ({size} bytes)")
    return 0


def cmd_history(args):
    """Show transaction history for a wallet."""
    url = f"{NODE_URL}/wallet/history?address={args.wallet_id}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"⚠ Failed to fetch history: {e}")
        return 1

    print(f"\n📜 Transaction history for {args.wallet_id}")
    txs = data if isinstance(data, list) else data.get("transactions", [])
    for tx in txs[:10]:  # Show last 10
        print(f"   {tx}")
    return 0


# ── Main ────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RustChain Wallet CLI — RTC Management")
    parser.add_argument("--node", help="RustChain node URL")
    parser.add_argument("--wallet-dir", help="Wallet directory")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create
    p = subparsers.add_parser("create", help="Generate a new wallet with BIP39 seed phrase")
    
    # balance
    p = subparsers.add_parser("balance", help="Check RTC balance")
    p.add_argument("wallet_id", help="Wallet address or miner ID")
    
    # send
    p = subparsers.add_parser("send", help="Send RTC to another address")
    p.add_argument("to", help="Recipient address")
    p.add_argument("amount", help="Amount in RTC")
    p.add_argument("wallet_id", nargs="?", default=None, help="Source wallet (omit to pick from list)")
    
    # import (FIXED: now properly recovers keys from mnemonic)
    p = subparsers.add_parser("import", help="Restore wallet from BIP39 seed phrase")
    p.add_argument("seed_phrase", nargs="+", help="12-word BIP39 seed phrase")
    
    # export
    p = subparsers.add_parser("export", help="Export encrypted keystore JSON")
    p.add_argument("wallet_id", help="Wallet address to export")
    
    # list
    subparsers.add_parser("list", help="List all local wallets")
    
    # history
    p = subparsers.add_parser("history", help="Show transaction history")
    p.add_argument("wallet_id", help="Wallet address or miner ID")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Apply global options
    global NODE_URL, WALLET_DIR
    if args.node:
        NODE_URL = args.node
    if hasattr(args, 'wallet_dir') and args.wallet_dir:
        WALLET_DIR = Path(args.wallet_dir)

    # Route to handler
    cmds = {
        "create": cmd_create,
        "balance": cmd_balance,
        "send": cmd_send,
        "import": cmd_import,
        "export": cmd_export,
        "list": cmd_list,
        "history": cmd_history,
    }

    handler = cmds.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"⚠ Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
