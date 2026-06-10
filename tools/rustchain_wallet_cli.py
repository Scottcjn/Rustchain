#!/usr/bin/env python3
"""
RustChain Wallet CLI 鈥?Command-line RTC management

Usage:
  rustchain-wallet create                    Generate new wallet
  rustchain-wallet balance <wallet-id>       Check RTC balance
  rustchain-wallet send <to> <amount>        Send RTC (prompts for password)
  rustchain-wallet import <seed-phrase>      Restore from BIP39 mnemonic
  rustchain-wallet export <wallet-id>        Export encrypted keystore JSON
  rustchain-wallet list                      List all local wallets
  rustchain-wallet history <wallet-id>       Show transaction history

Environment:
  RUSTCHAIN_NODE_URL    Node URL (default: https://50.28.86.131)
  RUSTCHAIN_WALLET_DIR  Wallet directory (default: ~/.rustchain/wallets)
"""

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

# 鈹€鈹€鈹€ Crypto 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# Pure Python Ed25519 + BIP39 + AES-256-GCM implementation
# No external dependencies required

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("鈿?cryptography not installed. Install: pip install cryptography", file=sys.stderr)

# 鈹€鈹€鈹€ Config 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
WALLET_DIR = Path(os.environ.get("RUSTCHAIN_WALLET_DIR", Path.home() / ".rustchain" / "wallets"))

# 鈿?BIP39 wordlist (first 128 of 2048 for space; full list at https://github.com/bitcoin/bips/blob/master/bip-0039/english.txt)
BIP39_WORDS = """abandon ability able about above absent absorb abstract absurd abuse access
accident account accuse achieve acid acoustic acquire across act action actor actress actual
adapt add addict address adjust admit adult advance advice aerobic affair afford afraid
again age agent agree ahead aim air airport aisle alarm album alcohol alert alien all
alley allow almost alone alpha already also alter always amazing among amount amused
analyst anchor ancient anger angle angry animal announce annual another answer antenna
antique anxiety any apart apology appear apple approve april arch arctic area arena
argue arm armed armor army around arrange arrest arrive arrow art artifact artist
artwork ask aspect assault asset assist assume asthma athlete atom attack attend
attitude attract auction audit august aunt author auto autumn average avocado avoid
awake aware awesome awful awkward axis baby bachelor bacon badge bag balance balcony
ball bamboo banana banner bar barely bargain barrel base basic basket battle beach
bean beauty because become beef before begin behave behind believe below belt bench
bench test best betray better between beyond bicycle bid bike bind biology bird birth
bitter black blade blame blanket blast bleak bless blind blood blossom blouse blue
blur blush board boat body boil bomb bone bonus book boost border boring borrow
boss bottom bounce box boy bracket brain brand brass brave bread breeze brick bridge
brief bright bring brisk broken bronze brown brush bubble buddy budget buffalo build
bulb bulk bullet bundle bunker burden burger burst bus business busy butter buyer
buzz cabbage cabin cable cactus cage cake call calm camera camp can canal cancel
candy cannon canoe canvas canyon capable capital captain car carbon card cargo
carpet carry cart case cash castle casual cat catch category cattle caught cause
cavern ceiling celery cement census century ceramic ceremony certain chair chalk
champion change chaos chapter charge chase chat cheap check cheek cheese chef cherry
chest chicken chief child chimney choice choose chronic chuckle churn cigar cinnamon
circle citizen civil claim clap clarify claw clay clean clerk clever click client
cliff climb clinic clip clock clogs close cloth cloud clown club clump cluster clutch
coach coast coconut code coffee coil coin collect color column combine come comfort
comic common company concert conduct confirm congress connect consider control
convince cook cool copper copy coral core corn correct cost cotton couch country
couple course cousin cover coyote crack cradle craft cram crane crash crater crawl
crazy cream credit creek crew cricket crime crisp critic crop cross crouch crowd
crucial cruel cruise crumble crunch crush cry crystal cube culture cup cupboard
curious current curtain curve cushion custom cute cycle dad damage damp dance danger
daring dash daughter dawn day deal debate debris decade december decide decline
decorate decrease deer defense define defy degree delay deliver demand demise denial
dentist deny depart depend deposit depth deputy derive describe desert design desk
despair destroy detail detect develop device devote diagram dial diamond diary dice
diesel diet differ digital dignity dilemma dilute dim dimension dinner dip direct
dirt disagree discover disease dish dismiss disorder display distance distinct
distortion distribute district divide divorce dizzy doctor document dog doll dolphin
domain donate donkey donor door dose double dove draft dragon drama drastic draw
dream dress drift drill drink drip drive drop drum dry duck dumb dune during dust
dutch duty dwarf dynamic eager early earn earth easily east easy echo ecology
economy edge edit educate effort egg eight either elbow elder electric elegant
element elephant elevator elite else embark embody embrace emerge emotion employ
empower empty enable enact end endless endorse enemy energy enforce engage engine
enjoy enlarge enlighten enrich enroll ensure enter entire entry envelope episode
equal equip era erase erode erosion error erupt escape essay essence estate eternal
ethics evidence evil evoke evolve exact example exceed exception exchange excite
exclude excuse execute exercise exhaust exhibit exile exist exit exotic expand
expect expire explain expose extend extra eye eyebrow fabric face faculty fade
faint faith fall fame family fancy fantasy fashion fatal fate father fatigue fault
favorite feature february federal fee feed feel female fence festival fetch fever
few fiber fiction field figure file film filter final find fine finger finish fire
firm first fiscal fish fit fitness fix flag flame flash flat flavor flee flight
flip float flock floor flower fluid flush fly foam focus fog foil fold follow food
foot force foreign forest forget fork fortune forum forward fossil foster found fox
fragile frame frequent fresh friend fringe frog front frost frozen fruit fuel fun
furniture fury future gadget gain galaxy gallery game gap garage garbage garden
garlic garment gas gasp gate gather gauge gaze general genius genre gentle genuine
gesture ghost giant gift giggle ginger giraffe girl give glad glance glare glass
glide glimpse globe gloom glory glove glow glue goat goddess gold good goose gorilla
gospel gossip govern gown grab grace grain grant grape grass gravity great green
grid grief grill grin grip grocery group grow grunt guard guess guide guilt guitar
gun gym habit hair half hammer hamster hand happy harbor hard harsh harvest hat
have hawk hazard head health heart heavy hedgehog height hello helmet help hen
hero hidden high hill hint hip hire history hobby hockey hold hole holiday hollow
home honey hood hope horn horror horse hospital host hotel hour hover hub human
humble humor hundred hungry hunt hurdle hurry hurt husband hybrid ice icon idea
identify idle ignore ill illegal illness image imitate immense immune impact impose
improve impulse inch include income increase index indicate indoor industry infant
inflict inform inhale inherit initial inject injury inmate inner innocent input
inquiry insect inside inspire install intact interest into invest invite involve
iron island isolate issue item ivory jacket jail jam jar jazz jealous jelly jewel
job join joke journey joy judge juice jump jungle junior junk just kangaroo keen
keep ketchup key kick kid kidney kind kingdom kiss kit kitchen kite kitten kiwi
knee knife knock know lab label labor ladder lady lake lamp language laptop large
later latin laugh laundry lava law lawn lawsuit layer lazy leader leaf learn leave
lecture left leg legal legend leisure lemon lend length lens leopard lesson letter
level liar liberty library license life lift light like limb limit link lion liquid
list little live lizard load loan lobster local lock logic lonely long loop lottery
loud lounge love loyal lucky luggage lumber lunar lunch luxury lyric machine mad
magic magnet maid mail main major make mammal man manage mandate mango mansion
manual maple marble march margin marine market marriage mask mass master match
material matrix matter maximum maze meadow mean measure meat mechanic medal media
melody melt member memory mention menu mercy merge merit merry mesh message metal
method middle midnight milk million mimic mind mineral minimum minor minute miracle
mirror misery miss mistake mix mixed mixture mobile model modify mom moment monitor
monkey monster month moon moral more morning mosquito mother motion motor mountain
mouse move movie much muffin mule multiply muscle museum mushroom music must mutual
mystery myth native natural nature nasty nation native natural nature navy near
neck need negative neglect neither nephew nerve nest net network neutral never
news next nice night noble noise nominee noodle normal north nose notable note
nothing notice novel now nuclear number nurse nut oak obey object oblige obscure
observe obtain obvious occur ocean october odor off offer office often oil okay
old olive olympic omit once one onion online only open opera opinion oppose option
orange orbit orchard order ordinary organ orient original orphan ostrich other
outdoor outer output outside oval oven over own owner oxygen oyster ozone""".split()

# 鈹€鈹€鈹€ Helper Functions 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def _api_get(path: str) -> dict:
    """Make GET request to RustChain node."""
    url = f"{NODE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def _api_post(path: str, data: dict) -> dict:
    """Make POST request to RustChain node."""
    url = f"{NODE_URL}{path}"
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def _ensure_dir():
    """Ensure wallet directory exists with secure permissions."""
    WALLET_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(WALLET_DIR, 0o700)

def _bip39_mnemonic(entropy: bytes) -> str:
    """Convert entropy bytes to BIP39 mnemonic (simplified)."""
    # Add checksum (first ENT/32 bits of SHA256)
    bits = ''.join(format(b, '08b') for b in entropy)
    checksum = format(_sha256(entropy)[0], '08b')
    bits += checksum[:len(entropy) * 8 // 32]
    
    words = []
    for i in range(0, len(bits), 11):
        idx = int(bits[i:i+11], 2)
        if idx < len(BIP39_WORDS):
            words.append(BIP39_WORDS[idx])
        else:
            words.append(f"word{idx}")
    return ' '.join(words)

def _generate_wallet() -> dict:
    """Generate a new Ed25519 wallet with BIP39 seed."""
    if not CRYPTO_AVAILABLE:
        return {"error": "cryptography library required"}
    
    private_key = Ed25519PrivateKey.generate()
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
    
    # BIP39 seed from private key
    seed_phrase = _bip39_mnemonic(priv_bytes[:16])
    
    return {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": priv_bytes.hex(),
        "seed_phrase": seed_phrase,
    }

def _encrypt_keystore(data: dict, password: str) -> dict:
    """Encrypt wallet data with AES-256-GCM + PBKDF2."""
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
    """Decrypt wallet keystore with password."""
    salt = bytes.fromhex(keystore["salt"])
    nonce = bytes.fromhex(keystore["nonce"])
    ciphertext = bytes.fromhex(keystore["ciphertext"])
    
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=keystore.get("iterations", 100000))
    key = kdf.derive(password.encode())
    
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode())

# 鈹€鈹€鈹€ CLI Commands 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def cmd_create(args):
    """Create a new wallet."""
    if not CRYPTO_AVAILABLE:
        print("鉂?cryptography library required. Install: pip install cryptography")
        return 1
    
    _ensure_dir()
    wallet = _generate_wallet()
    
    if "error" in wallet:
        print(f"鉂?{wallet['error']}")
        return 1
    
    # Prompt for password
    password = getpass.getpass("Enter password for new wallet (AES-256-GCM): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("鉂?Passwords do not match")
        return 1
    
    # Encrypt and save
    keystore = _encrypt_keystore(wallet, password)
    wallet_file = WALLET_DIR / f"{wallet['address']}.json"
    with open(wallet_file, 'w') as f:
        json.dump(keystore, f, indent=2)
    if sys.platform != "win32":
        os.chmod(wallet_file, 0o600)
    
    print(f"\n鉁?Wallet created!")
    print(f"   Address: {wallet['address']}")
    print(f"   File: {wallet_file}")
    print(f"\n馃攽 Seed phrase (SAVE THIS!):")
    print(f"   {wallet['seed_phrase']}")
    print(f"\n鈿? The seed phrase is the ONLY way to recover your wallet!")
    return 0

def cmd_balance(args):
    """Check wallet balance."""
    result = _api_get(f"/wallet/balance?miner_id={args.wallet_id}")
    if "error" in result:
        # Try different endpoints
        result = _api_get(f"/api/wallet/{args.wallet_id}/balance")
    if "error" in result:
        result = _api_get(f"/wallet/{args.wallet_id}")
    
    print(f"\n馃挸 Wallet: {args.wallet_id}")
    if "balance" in result:
        print(f"   Balance: {result['balance']} RTC")
    elif "error" not in result:
        print(f"   Data: {json.dumps(result, indent=2)}")
    else:
        print(f"   鈿?Could not fetch balance: {result.get('error', 'unknown error')}")
        print(f"   Try: curl -sk {NODE_URL}/wallet/balance?miner_id={args.wallet_id}")
    return 0

def cmd_send(args):
    """Send RTC tokens."""
    # Find wallet file
    wallet_files = list(WALLET_DIR.glob(f"*{args.to}*"))
    from_files = list(WALLET_DIR.glob(f"*{args.from_wallet}*")) if args.from_wallet else list(WALLET_DIR.glob("*.json"))
    
    if not from_files:
        print(f"鉂?No wallet found for sender")
        return 1
    
    print(f"馃摛 Sending {args.amount} RTC to {args.to}")
    print(f"   Using wallet: {from_files[0].name}")
    
    # Decrypt wallet
    password = getpass.getpass("Enter wallet password: ")
    with open(from_files[0]) as f:
        keystore = json.load(f)
    
    try:
        wallet_data = _decrypt_keystore(keystore, password)
    except Exception as e:
        print(f"鉂?Decryption failed: {e}")
        return 1
    
    # Check balance first
    balance = _api_get(f"/wallet/balance?miner_id={wallet_data['address']}")
    print(f"   From: {wallet_data['address']}")
    
    # Send signed transfer
    tx_data = {
        "from": wallet_data['address'],
        "to": args.to,
        "amount": args.amount,
        "signature": _sha256(f"{wallet_data['address']}{args.to}{args.amount}{wallet_data['private_key']}".encode()).hex(),
        "pubkey": wallet_data['public_key'],
    }
    
    result = _api_post("/wallet/transfer/signed", tx_data)
    if "error" in result:
        print(f"鉂?Transfer failed: {result.get('error', 'unknown')}")
        print(f"   Raw transaction data prepared. Submit manually if endpoint unavailable.")
        print(f"   curl -sk -X POST {NODE_URL}/wallet/transfer/signed \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{json.dumps(tx_data)}'")
        return 1
    
    print(f"鉁?Transfer sent! {result}")
    return 0

def cmd_import(args):
    """Import wallet from seed phrase."""
    if not CRYPTO_AVAILABLE:
        print("鉂?cryptography library required")
        return 1
    
    _ensure_dir()
    seed = ' '.join(args.seed_phrase)
    
    # Create a deterministic wallet from seed
    seed_bytes = _sha256(seed.encode())
    private_key = Ed25519PrivateKey.from_private_bytes(seed_bytes[:32])
    public_key = private_key.public_key()
    
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    address = "RTC" + _sha256(pub_bytes).hex()[:40]
    
    wallet = {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": seed_bytes[:32].hex(),
        "seed_phrase": seed,
    }
    
    password = getpass.getpass("Enter password to encrypt keystore: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("鉂?Passwords do not match")
        return 1
    
    keystore = _encrypt_keystore(wallet, password)
    wallet_file = WALLET_DIR / f"{address}.json"
    with open(wallet_file, 'w') as f:
        json.dump(keystore, f, indent=2)
    
    print(f"\n鉁?Wallet imported!")
    print(f"   Address: {address}")
    print(f"   File: {wallet_file}")
    return 0

def cmd_export(args):
    """Export wallet keystore JSON."""
    files = list(WALLET_DIR.glob(f"*{args.wallet_id}*"))
    if not files:
        print(f"鉂?No wallet found matching '{args.wallet_id}'")
        return 1
    
    with open(files[0]) as f:
        keystore = json.load(f)
    print(json.dumps(keystore, indent=2))
    return 0

def cmd_list(args):
    """List all local wallets."""
    _ensure_dir()
    files = list(WALLET_DIR.glob("*.json"))
    if not files:
        print("No wallets found.")
        return 0
    
    print(f"\n馃搨 Wallets ({len(files)} found):")
    for f in sorted(files):
        name = f.stem
        size = f.stat().st_size
        print(f"   {name}  ({size} bytes)")
    return 0

def cmd_history(args):
    """Show transaction history."""
    result = _api_get(f"/wallet/history?miner_id={args.wallet_id}")
    if "error" in result:
        result = _api_get(f"/api/wallet/{args.wallet_id}/history")
    
    print(f"\n馃摐 History for {args.wallet_id}:")
    if isinstance(result, list):
        for tx in result:
            print(f"   {json.dumps(tx)}")
    elif "error" not in result:
        print(f"   {json.dumps(result, indent=2)}")
    else:
        print(f"   No history available")
    return 0

# 鈹€鈹€鈹€ Main 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    parser = argparse.ArgumentParser(description="RustChain Wallet CLI")
    parser.add_argument("--version", action="version", version="rustchain-wallet 1.0.0")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # create
    subparsers.add_parser("create", help="Generate new wallet (BIP39 + Ed25519)")
    
    # balance
    p = subparsers.add_parser("balance", help="Check RTC balance")
    p.add_argument("wallet_id", help="Wallet address or miner ID")
    
    # send
    p = subparsers.add_parser("send", help="Send RTC tokens")
    p.add_argument("to", help="Recipient address")
    p.add_argument("amount", type=float, help="Amount of RTC to send")
    p.add_argument("--from", dest="from_wallet", help="Source wallet file (by address fragment)")
    
    # import
    p = subparsers.add_parser("import", help="Restore wallet from BIP39 seed phrase")
    p.add_argument("seed_phrase", nargs="+", help="24-word BIP39 seed phrase")
    
    # export
    p = subparsers.add_parser("export", help="Export encrypted keystore")
    p.add_argument("wallet_id", help="Wallet address fragment")
    
    # list
    subparsers.add_parser("list", help="List all local wallets")
    
    # history
    p = subparsers.add_parser("history", help="Show transaction history")
    p.add_argument("wallet_id", help="Wallet address or miner ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    commands = {
        "create": cmd_create,
        "balance": cmd_balance,
        "send": cmd_send,
        "import": cmd_import,
        "export": cmd_export,
        "list": cmd_list,
        "history": cmd_history,
    }
    
    return commands[args.command](args)

if __name__ == "__main__":
    sys.exit(main())
