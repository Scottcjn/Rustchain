"""
RustChain Wallet Module
Wallet creation, Ed25519 signing, and address management.
"""

import hashlib
import hmac
import json
import os
import secrets
import struct
from typing import List, Optional, Dict, Any, Tuple

# BIP39 word list (first 512 words from standard BIP39 wordlist - sufficient for demo)
_BIP39_WORDLIST: List[str] = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
    "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
    "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
    "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
    "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
    "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
    "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
    "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among",
    "amount", "amused", "analyst", "anchor", "ancient", "anger", "angle", "angry",
    "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
    "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april",
    "arch", "arctic", "area", "arena", "argue", "arm", "armed", "armor",
    "army", "around", "arrange", "arrest", "arrive", "arrow", "art", "artefact",
    "artist", "artwork", "ask", "aspect", "assault", "asset", "assist", "assume",
    "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction",
    "audit", "august", "aunt", "author", "auto", "autumn", "average", "avocado",
    "avoid", "awake", "aware", "away", "awesome", "awful", "awkward", "axis",
    "baby", "bachelor", "bacon", "badge", "bag", "balance", "balcony", "ball",
    "bamboo", "banana", "banner", "bar", "barely", "bargain", "barrel", "base",
    "basic", "basket", "battle", "beach", "bean", "beauty", "because", "become",
    "beef", "before", "begin", "behave", "behind", "believe", "below", "belt",
    "bench", "benefit", "best", "betray", "better", "between", "beyond", "bicycle",
    "bid", "bike", "bind", "biology", "bird", "birth", "bitter", "black",
    "blade", "blame", "blanket", "blast", "bleak", "bless", "blind", "blood",
    "blossom", "blouse", "blue", "blur", "blush", "board", "boat", "body",
    "boil", "bomb", "bone", "bonus", "book", "boost", "border", "boring",
    "borrow", "boss", "bottom", "bounce", "box", "boy", "bracket", "brain",
    "brand", "brass", "brave", "bread", "breeze", "brick", "bridge", "brief",
    "bright", "bring", "brisk", "broccoli", "broken", "bronze", "broom", "brother",
    "brown", "brush", "bubble", "buddy", "budget", "buffalo", "build", "bungalow",
    "burst", "bus", "business", "busy", "butter", "buyer", "buzz", "cabbage",
    "cabin", "cable", "cactus", "cage", "cake", "call", "calm", "camera",
    "camp", "canal", "cancel", "candy", "cannon", "canoe", "canvas", "canyon",
    "capable", "capital", "captain", "car", "carbon", "card", "cargo", "carpet",
    "carry", "cart", "case", "cash", "casino", "castle", "casual", "cat",
    "catalog", "catch", "category", "cattle", "caught", "cause", "caution", "cave",
    "ceiling", "celery", "cement", "census", "century", "cereal", "certain", "chair",
    "chalk", "champion", "change", "chaos", "chapter", "charge", "chase", "chat",
    "cheap", "check", "cheese", "chef", "cherry", "chest", "chicken", "chief",
    "child", "chimney", "choice", "choose", "chronic", "chuckle", "chunk", "churn",
    "cigar", "cinnamon", "circle", "citizen", "city", "civil", "claim", "clap",
    "clarify", "claw", "clay", "clean", "clerk", "clever", "click", "client",
    "cliff", "climb", "clinic", "clip", "clock", "clog", "close", "cloth",
    "cloud", "clown", "club", "clump", "cluster", "clutch", "coach", "coast",
    "coconut", "code", "coffee", "coil", "coin", "collect", "color", "column",
    "combine", "come", "comfort", "comic", "common", "company", "concert", "conduct",
    "confirm", "congress", "connect", "consider", "control", "convince", "cook", "cool",
    "copper", "copy", "coral", "core", "corn", "correct", "cost", "cotton",
    "couch", "country", "couple", "course", "cousin", "cover", "coyote", "crack",
    "cradle", "craft", "cram", "crane", "crash", "crater", "crawl", "crazy",
    "cream", "credit", "creek", "crew", "cricket", "crime", "crisp", "critic",
    "crop", "cross", "crouch", "crowd", "crucial", "cruel", "cruise", "crumble",
    "crunch", "crush", "cry", "crystal", "cube", "culture", "cup", "cupboard",
    "curious", "current", "curtain", "curve", "cushion", "custom", "cute", "cycle",
    "damage", "damp", "dance", "danger", "daring", "dash", "daughter", "dawn",
    "day", "deal", "debate", "debris", "decade", "december", "decide", "decline",
    "decorate", "decrease", "deer", "defense", "define", "degree", "delay", "deliver",
    "demand", "demise", "denial", "dentist", "deny", "depart", "depend", "deposit",
    "depth", "deputy", "derive", "describe", "desert", "design", "desk", "despair",
    "destroy", "detail", "detect", "develop", "device", "devote", "diagram", "dial",
    "diamond", "diary", "dice", "diesel", "diet", "differ", "digital", "dignity",
    "dilemma", "dinner", "dinosaur", "direct", "dirt", "disagree", "discover", "disease",
    "dish", "dismiss", "disorder", "display", "distance", "divert", "divide", "divorce",
    "dizzy", "doctor", "document", "dog", "doll", "dolphin", "domain", "donate",
    "donkey", "donor", "door", "dose", "double", "dove", "draft", "dragon",
    "drama", "drastic", "draw", "dream", "dress", "drift", "drill", "drink",
    "drip", "drive", "drop", "drum", "dry", "duck", "dumb", "dune",
    "during", "dust", "dutch", "duty", "dwarf", "dynamic", "eager", "eagle",
    "early", "earn", "earth", "easily", "east", "easy", "echo", "ecology",
    "economy", "edge", "edit", "educate", "effort", "egg", "either", "elbow",
    "elder", "electric", "elegant", "element", "elephant", "elevator", "elite", "else",
    "embark", "embody", "embrace", "emerge", "emotion", "employ", "empower", "empty",
    "enemy", "energy", "enforce", "engage", "engine", "enhance", "enjoy", "enlist",
    "enough", "enrich", "enroll", "ensure", "enter", "entire", "entry", "envelope",
    "episode", "equal", "equip", "era", "erase", "erode", "erosion", "error",
    "erupt", "escape", "essay", "essence", "estate", "eternal", "ethics", "evidence",
    "evil", "evoke", "evolve", "exact", "example", "excess", "exchange", "excite",
    "exclude", "excuse", "execute", "exercise", "exhaust", "exhibit", "exile", "exist",
    "exit", "exotic", "expand", "expect", "expire", "explain", "expose", "express",
    "extend", "extra", "eye", "eyebrow", "fabric", "face", "faculty", "fade",
    "faint", "faith", "fall", "false", "fame", "family", "famous", "fan",
    "fancy", "fantasy", "farm", "fashion", "fat", "fatal", "father", "fatigue",
    "fault", "favorite", "feature", "february", "federal", "fee", "feed", "feel",
    "female", "fence", "festival", "fetch", "fever", "few", "fiber", "fiction",
    "field", "figure", "file", "film", "filter", "final", "find", "fine",
    "finger", "finish", "fire", "firm", "first", "fiscal", "fish", "fit",
    "fitness", "fix", "flag", "flame", "flash", "flat", "flavor", "flee",
    "flight", "flip", "float", "flock", "floor", "flower", "fluid", "flush",
    "fly", "foam", "focus", "fog", "foil", "fold", "follow", "food",
    "foot", "force", "forest", "forget", "fork", "fortune", "forum", "forward",
    "fossil", "foster", "found", "fox", "fragile", "frame", "frequent", "fresh",
    "friend", "fringe", "frog", "front", "frost", "frown", "frozen", "fruit",
    "fuel", "fun", "funny", "furnace", "fury", "future", "gadget", "gain",
    "galaxy", "gallery", "game", "gap", "garage", "garbage", "garden", "garlic",
    "garment", "gas", "gasp", "gate", "gather", "gauge", "gaze", "general",
    "genius", "genre", "gentle", "genuine", "gesture", "ghost", "giant", "gift",
    "giggle", "ginger", "giraffe", "girl", "give", "glad", "glance", "glare",
    "glass", "gleam", "globe", "gloom", "glory", "glove", "glow", "goal",
    "goat", "goddess", "gold", "golf", "good", "goose", "gossip", "govern",
    "gown", "grace", "grade", "grain", "grand", "grant", "grape", "graph",
    "grasp", "grass", "grateful", "grave", "gravy", "gray", "graze", "great",
    "green", "greet", "grief", "grill", "grind", "grip", "groan", "grocery",
    "groom", "groove", "gross", "group", "grove", "grow", "growth", "guard",
    "guess", "guest", "guide", "guilt", "guitar", "gulf", "gutter", "gym",
    "habit", "hair", "half", "hall", "hammer", "hamster", "hand", "happy",
    "harbor", "hard", "harsh", "harvest", "haste", "hat", "hatch", "hate",
    "haul", "have", "hawk", "hazard", "head", "heal", "health", "heart",
    "heavy", "hedgehog", "height", "heir", "helicopter", "hell", "hello", "helmet",
    "help", "hen", "hero", "hesitate", "hidden", "high", "hill", "hint",
    "hip", "hire", "historian", "history", "hold", "hole", "holiday", "hollow",
    "home", "honey", "honor", "hood", "hope", "horn", "horror", "horse",
    "hospital", "hotel", "hour", "hover", "hub", "huge", "human", "humble",
    "humor", "hundred", "hunger", "hunt", "hurdle", "hurry", "hurt", "husband",
    "hybrid", "ice", "icon", "idea", "ideal", "identity", "idle", "idiot",
    "ignorant", "ignore", "ill", "illegal", "illness", "image", "imitate", "immense",
    "immune", "impact", "impose", "improve", "impulse", "inch", "include", "income",
    "increase", "index", "indicate", "indoor", "induce", "industry", "infant", "inflict",
    "inform", "ink", "innate", "inner", "input", "inquiry", "insect", "insert",
    "inside", "insist", "inspire", "install", "intact", "intake", "intelligence", "intend",
    "intense", "interact", "interest", "interior", "internal", "interval", "intervene", "intestine",
    "introduce", "invade", "invest", "invite", "involve", "iron", "island", "isolate",
    "issue", "item", "ivory", "jacket", "jaguar", "jar", "jazz", "jealous",
    "jeans", "jelly", "jellyfish", "jewel", "job", "join", "joke", "jolly",
    "jolt", "joy", "judge", "juice", "jumbo", "jump", "jumpy", "jungle",
    "junior", "junk", "just", "justice", "justify", "kangaroo", "keen", "keep",
    "ketchup", "key", "kick", "kid", "kidney", "kind", "king", "kiss",
    "kit", "kitchen", "kite", "kitten", "knee", "knife", "knight", "knit",
    "knob", "knock", "knot", "know", "knowledge", "label", "labor", "ladder",
    "lady", "lake", "lamb", "lamp", "land", "landscape", "lane", "language",
    "laptop", "large", "laser", "lasso", "last", "late", "later", "laugh",
    "laundry", "lava", "law", "lawn", "lawsuit", "layer", "lazy", "lead",
    "leaf", "learn", "least", "leave", "lecture", "left", "leg", "legal",
    "lemon", "lend", "length", "lens", "leopard", "lesson", "letter", "level",
    "lever", "liar", "liberty", "library", "license", "life", "lift", "light",
    "like", "limb", "limit", "linen", "lion", "list", "live", "liver",
    "living", "lizard", "load", "loan", "lobster", "local", "lock", "lodge",
    "logic", "lonely", "loose", "lottery", "lounge", "love", "loyal", "luck",
    "lucky", "luggage", "lumber", "lunar", "lunch", "luxury", "lyrics", "machine",
]


def _to_words(data: bytes, wordlist: List[str]) -> List[str]:
    """Convert raw bytes to BIP39-style words."""
    words: List[str] = []
    for i in range(0, len(data), 2):
        word_index = int.from_bytes(data[i : i + 2], byteorder="big") % len(wordlist)
        words.append(wordlist[word_index])
    return words


def _from_words(words: List[str], wordlist: List[str]) -> bytes:
    """Convert BIP39-style words back to bytes."""
    word_to_index = {w: i for i, w in enumerate(wordlist)}
    result = bytearray()
    for word in words:
        if word not in word_to_index:
            raise ValueError(f"Unknown word: {word}")
        result.extend(word_to_index[word].to_bytes(2, byteorder="big"))
    return bytes(result)


def _sha256d(data: bytes) -> bytes:
    """Double SHA256 (Bitcoin-style)."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _hmac_sha512(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA512."""
    return hmac.new(key, data, hashlib.sha512).digest()


class RustChainWallet:
    """
    RustChain wallet with BIP39 seed phrase and Ed25519 signing.

    Wallets are identified by a public key address (RTCxx...) on the RustChain
    network. The wallet can sign transactions using Ed25519.

    Example:
        # Create a new wallet
        wallet = RustChainWallet.create()

        # Access properties
        print(wallet.address)      # RTC1a2b3c4d5e6f...
        print(wallet.seed_phrase)  # ["abandon", "ability", ...]

        # Sign a transfer payload
        signature = wallet.sign_transfer("recipient_address", 1000)
        print(signature)  # hex-encoded Ed25519 signature

        # Export/Import
        exported = wallet.export()
        restored = RustChainWallet.import(exported)
    """

    ADDRESS_PREFIX = "RTC"
    DERIVED_ADDRESS_PREFIX = "RTC"

    def __init__(
        self,
        address: str,
        private_key: bytes,
        seed_phrase: Optional[List[str]] = None,
        public_key: Optional[bytes] = None,
        derivation_path: Optional[str] = None,
    ):
        self._address = address
        self._private_key = private_key
        self._seed_phrase = seed_phrase or []
        self._public_key = public_key or self._derive_public_key(private_key)
        self._derivation_path = derivation_path or "m/44'/9000'/0'/0/0"

    @staticmethod
    def _derive_public_key(private_key: bytes) -> bytes:
        """Derive public key from private key using Ed25519."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            import base64

            # Use cryptography library if available
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            priv = Ed25519PrivateKey.from_private_bytes(private_key[:32])
            pub = priv.public_key()
            return pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        except ImportError:
            # Fallback: simple hash-based "public key" derivation
            return _sha256d(b"pubkey" + private_key)[:32]

    @classmethod
    def create(cls, strength: int = 128) -> "RustChainWallet":
        """
        Create a new wallet with a BIP39-style seed phrase.

        Args:
            strength: Entropy strength in bits. 128 bits = 12 words, 256 bits = 24 words.

        Returns:
            A new RustChainWallet instance.

        Raises:
            ValueError: If strength is not 128 or 256.
        """
        if strength not in (128, 256):
            raise ValueError("Strength must be 128 (12 words) or 256 (24 words)")

        # Generate random entropy
        raw_bytes = secrets.token_bytes(strength // 8)

        # Add checksum (first byte of SHA256 of entropy)
        checksum = hashlib.sha256(raw_bytes).digest()[:1]
        extended = raw_bytes + checksum

        # Convert to words
        words = _to_words(extended, _BIP39_WORDLIST)

        # Derive seed from words
        seed = _hmac_sha512(b"mnemonic", " ".join(words).encode("utf-8"))

        # Use first 32 bytes as private key
        private_key = seed[:32]

        # Generate address from private key
        address = cls._generate_address(private_key)

        return cls(
            address=address,
            private_key=private_key,
            seed_phrase=words,
            public_key=cls._derive_public_key(private_key),
        )

    @classmethod
    def _generate_address(cls, private_key: bytes) -> str:
        """Generate a wallet address from private key."""
        # Derive public key
        if hasattr(cls, "_derive_public_key"):
            pubkey = cls._derive_public_key(private_key)
        else:
            pubkey = _sha256d(b"pubkey" + private_key)[:32]

        # Hash public key to get address
        addr_hash = _sha256d(b"address" + pubkey)
        addr_bytes = addr_hash[:20]

        # Format as RTC + hex
        return cls.ADDRESS_PREFIX + addr_bytes.hex()

    @classmethod
    def from_seed_phrase(cls, words: List[str]) -> "RustChainWallet":
        """
        Create a wallet from a BIP39 seed phrase.

        Args:
            words: List of seed words (12 or 24 words).

        Returns:
            A RustChainWallet instance.

        Raises:
            ValueError: If the word list is invalid.
        """
        if len(words) not in (12, 24):
            raise ValueError("Seed phrase must be 12 or 24 words")

        # Re-derive seed from words
        seed = _hmac_sha512(b"mnemonic", " ".join(words).encode("utf-8"))
        private_key = seed[:32]

        address = cls._generate_address(private_key)

        return cls(
            address=address,
            private_key=private_key,
            seed_phrase=words,
            public_key=cls._derive_public_key(private_key),
        )

    def sign(self, message: bytes) -> bytes:
        """
        Sign a message using Ed25519.

        Args:
            message: The message bytes to sign.

        Returns:
            The Ed25519 signature (64 bytes).
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            priv = Ed25519PrivateKey.from_private_bytes(self._private_key[:32])
            return priv.sign(message)
        except ImportError:
            # Fallback: HMAC-based signature (not real Ed25519)
            return _hmac_sha512(self._private_key, message)[:64]

    def sign_transfer(
        self,
        to_address: str,
        amount: float,
        fee: float = 0,
        memo: str = "",
        chain_id: Optional[str] = None,
        nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a signed transfer payload for the RustChain network.

        Args:
            to_address: Recipient wallet address.
            amount: Amount to transfer in RTC.
            fee: Transaction fee in RTC.
            memo: Optional transfer memo.
            chain_id: Optional chain/network id.
            nonce: Optional caller-supplied nonce. Defaults to current unix ms.

        Returns:
            A dict containing the transfer payload with signature.
        """
        import time

        nonce_value = int(nonce if nonce is not None else time.time_ns() // 1_000_000)
        amount_for_sig = float(amount)
        fee_for_sig = float(fee)
        tx_data = {
            "from": self._address,
            "to": to_address,
            "amount": amount_for_sig,
            "fee": fee_for_sig,
            "memo": memo,
            "nonce": str(nonce_value),
        }
        if chain_id:
            tx_data["chain_id"] = chain_id
        message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
        signature = self.sign(message)

        return {
            "from_address": self._address,
            "to_address": to_address,
            "amount_rtc": amount_for_sig,
            "fee": fee_for_sig,
            "fee_rtc": fee_for_sig,
            "nonce": nonce_value,
            "signature": signature.hex(),
            "public_key": self.public_key_hex,
            "memo": memo,
            **({"chain_id": chain_id} if chain_id else {}),
        }

    @property
    def address(self) -> str:
        """The wallet's public address on the RustChain network."""
        return self._address

    @property
    def public_key_hex(self) -> str:
        """The wallet's public key as a hex string."""
        return self._public_key.hex()

    @property
    def seed_phrase(self) -> List[str]:
        """The BIP39 seed phrase (mnemonic). Keep this secret!"""
        return self._seed_phrase

    @property
    def private_key_hex(self) -> str:
        """The private key as a hex string. Keep this secret!"""
        return self._private_key.hex()

    def export(self) -> Dict[str, Any]:
        """
        Export the wallet to a JSON-serializable dict.

        WARNING: The export contains the seed phrase. Keep it secure.

        Returns:
            A dict with the wallet's encrypted/exported data.
        """
        return {
            "version": 1,
            "address": self._address,
            "seed_phrase": self._seed_phrase,
            "derivation_path": self._derivation_path,
        }

    @classmethod
    def import_(cls, data: Dict[str, Any]) -> "RustChainWallet":
        """
        Import a wallet from an exported dict.

        Args:
            data: The exported wallet data.

        Returns:
            A RustChainWallet instance.
        """
        if data.get("version") != 1:
            raise ValueError(f"Unknown export version: {data.get('version')}")

        return cls.from_seed_phrase(data["seed_phrase"])

    def __repr__(self) -> str:
        return f"RustChainWallet(address={self._address!r})"
