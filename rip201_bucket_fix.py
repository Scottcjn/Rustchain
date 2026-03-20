#!/usr/bin/env python3
"""
RIP-201 Bucket Normalization Spoofing Fix
==========================================

Bounty #554: A modern x86 CPU (e.g., Intel Xeon Platinum) can claim
device_arch=G4 (PowerPC) and get routed into the vintage_powerpc bucket
with a 2.5x reward multiplier -- a 10x gain over honest miners.

This module adds server-side defences:

1. CPU brand-string cross-validation against claimed device_arch.
2. SIMD evidence requirement for vintage PowerPC claims (AltiVec / vec_perm).
3. Cache-timing profile validation matching PowerPC characteristics.
4. Server-side bucket classification derived from *verified* hardware
   features rather than raw client-reported architecture strings.

Designed to be imported by ``node/rewards_implementation_rip200.py`` and
called before a miner's ``device_arch`` is accepted for reward weighting.

Follows Rustchain patterns: raw sqlite3, Flask-compatible, no ORM.
"""

import re
import sqlite3
import time
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

# ---------------------------------------------------------------------------
# 1. CPU brand-string cross-validation
# ---------------------------------------------------------------------------

# Patterns that positively identify a modern x86 vendor/product line.
_MODERN_X86_BRAND_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"Intel\(R\)\s*(Core|Xeon|Celeron|Pentium|Atom)",
        r"Intel.*Core.*i[3579]",
        r"Intel.*Xeon",
        r"Genuine\s*Intel",
        r"AMD\s*(Ryzen|EPYC|Athlon|Opteron|Phenom|FX|Threadripper)",
        r"AMD.*EPYC",
        r"AuthenticAMD",
        # VIA / Centaur modern chips
        r"VIA\s*(Nano|C7|Eden|Quadcore)",
        r"CentaurHauls",
    ]
]

# Architectures that are *not* x86 -- the vintage/RISC buckets.
_NON_X86_ARCHS = frozenset({
    "g3", "g4", "g5", "power8", "sparc", "68k", "amiga_68k",
    "apple_silicon", "arm64", "riscv",
})

# Architectures that specifically require PowerPC lineage.
_POWERPC_ARCHS = frozenset({"g3", "g4", "g5", "power8"})

# Expected brand substrings for PowerPC claims.
_POWERPC_BRAND_KEYWORDS = [
    "motorola", "freescale", "nxp", "ibm", "power macintosh",
    "powerbook", "powermac", "power mac", "amigaone", "pegasos",
    "sam440", "sam460", "ppc", "powerpc",
]


def _brand_looks_modern_x86(brand: str) -> bool:
    """Return True if the brand string matches a known modern x86 CPU."""
    if not brand:
        return False
    return any(pat.search(brand) for pat in _MODERN_X86_BRAND_PATTERNS)


def _brand_looks_powerpc(brand: str) -> bool:
    """Return True if the brand string plausibly belongs to a PowerPC system."""
    if not brand:
        return False
    lower = brand.lower()
    return any(kw in lower for kw in _POWERPC_BRAND_KEYWORDS)


def validate_cpu_brand_vs_arch(
    cpu_brand: str,
    claimed_arch: str,
) -> Tuple[bool, str]:
    """Cross-validate CPU brand string against claimed architecture.

    Returns (passed, reason).  ``passed=False`` means the claim is
    rejected outright -- e.g. an Intel Xeon claiming G4.
    """
    if not claimed_arch:
        return False, "missing_device_arch"

    arch_lower = claimed_arch.lower().strip()

    # Only gate non-x86 claims.  Modern x86 miners claiming modern_x86
    # don't need brand gating -- they're honest.
    if arch_lower not in _NON_X86_ARCHS:
        return True, "arch_not_gated"

    # Hard reject: modern x86 brand + non-x86 arch claim.
    if _brand_looks_modern_x86(cpu_brand):
        return False, (
            f"brand_arch_conflict:brand_is_modern_x86,"
            f"claimed_arch={claimed_arch}"
        )

    # For PowerPC claims, additionally require a PowerPC-plausible brand.
    # An empty/missing brand is not sufficient -- we need positive evidence.
    if arch_lower in _POWERPC_ARCHS:
        if not _brand_looks_powerpc(cpu_brand or ""):
            return False, (
                f"brand_not_powerpc:brand={cpu_brand},"
                f"claimed_arch={claimed_arch}"
            )

    return True, "brand_ok"


# ---------------------------------------------------------------------------
# 2. SIMD evidence requirement for vintage PowerPC
# ---------------------------------------------------------------------------

def validate_simd_evidence(
    claimed_arch: str,
    simd_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """Require AltiVec / vec_perm evidence for G4/G5 PowerPC claims.

    G3 does *not* have AltiVec, so we skip that check for G3.
    Power8/9 also has AltiVec (IBM VMX).

    Returns (passed, reason).
    """
    arch_lower = (claimed_arch or "").lower().strip()
    altivec_archs = {"g4", "g5", "power8"}

    if arch_lower not in altivec_archs:
        return True, "simd_check_not_required"

    if not simd_data or not isinstance(simd_data, dict):
        return False, f"missing_simd_data:claimed_arch={arch_lower}"

    # Accept nested { "data": { ... } } or flat dict.
    data = simd_data.get("data", simd_data)
    if not isinstance(data, dict):
        data = simd_data

    has_altivec = bool(data.get("has_altivec", False))
    if not has_altivec:
        return False, f"altivec_missing:claimed_arch={arch_lower}"

    # vec_perm is a strong AltiVec indicator (used by real G4 miners).
    vec_perm = data.get("vec_perm_result")
    altivec_ops = data.get("altivec_ops")
    simd_type = (data.get("simd_type") or "").lower()

    # Must not simultaneously claim x86 SIMD features.
    for x86_feat in ("has_sse2", "has_avx", "has_avx2", "has_avx512"):
        if data.get(x86_feat, False):
            return False, (
                f"x86_simd_with_altivec:feat={x86_feat},"
                f"claimed_arch={arch_lower}"
            )

    # Require either vec_perm evidence, altivec_ops count, or simd_type
    # explicitly set to "altivec".
    if vec_perm is None and altivec_ops is None and simd_type != "altivec":
        return False, (
            f"insufficient_altivec_evidence:claimed_arch={arch_lower}"
        )

    return True, "simd_evidence_ok"


# ---------------------------------------------------------------------------
# 3. Cache-timing profile validation for PowerPC
# ---------------------------------------------------------------------------

# PowerPC G4 characteristics:
#   - L1 32 KB, L2 256 KB-1 MB (on-chip or backside)
#   - No L3 on G4 (7450/7447)
#   - Higher cache-miss variance than modern x86
#   - Coefficient of variation (CV) typically 0.01 - 0.15 (vs < 0.008 on x86)
#
# We codify these as min/max bounds.  Values outside the window indicate
# the miner is running on hardware inconsistent with G4/G5.

@dataclass
class _CacheProfile:
    """Expected cache-timing characteristics for an architecture."""
    cv_min: float
    cv_max: float
    tone_ratio_min: float   # min mean tone_ratio (L(n+1)/L(n) latency ratio)
    tone_ratio_max: float
    max_cache_levels: int   # e.g. G4 has L1+L2 only => 2
    require_no_large_l3: bool = False  # G4 should NOT have a big L3

# Profiles keyed by normalized arch.
_CACHE_PROFILES: Dict[str, _CacheProfile] = {
    "g4": _CacheProfile(
        cv_min=0.008, cv_max=0.15,
        tone_ratio_min=0.8, tone_ratio_max=8.0,
        max_cache_levels=3,       # L1 + L2 (+ small L3 on some)
        require_no_large_l3=True, # No 4096 KB+ L3
    ),
    "g5": _CacheProfile(
        cv_min=0.005, cv_max=0.12,
        tone_ratio_min=0.7, tone_ratio_max=10.0,
        max_cache_levels=4,
        require_no_large_l3=False,
    ),
    "g3": _CacheProfile(
        cv_min=0.01, cv_max=0.20,
        tone_ratio_min=0.5, tone_ratio_max=6.0,
        max_cache_levels=2,
        require_no_large_l3=True,
    ),
}


def validate_cache_timing(
    claimed_arch: str,
    cache_data: Dict[str, Any],
    clock_data: Dict[str, Any],
) -> Tuple[bool, str]:
    """Validate cache-timing profile matches PowerPC characteristics.

    For non-PowerPC arches this is a no-op pass.

    Returns (passed, reason).
    """
    arch_lower = (claimed_arch or "").lower().strip()
    profile = _CACHE_PROFILES.get(arch_lower)
    if profile is None:
        return True, "cache_profile_check_not_required"

    # --- Clock CV check ---
    if clock_data and isinstance(clock_data, dict):
        cd = clock_data.get("data", clock_data)
        if isinstance(cd, dict):
            cv = cd.get("cv", 0)
            if cv and cv < profile.cv_min:
                return False, (
                    f"clock_cv_too_low:cv={cv:.6f},"
                    f"min={profile.cv_min},"
                    f"claimed_arch={arch_lower}"
                )
            if cv and cv > profile.cv_max:
                return False, (
                    f"clock_cv_too_high:cv={cv:.6f},"
                    f"max={profile.cv_max},"
                    f"claimed_arch={arch_lower}"
                )

    # --- Cache structure check ---
    if cache_data and isinstance(cache_data, dict):
        cd = cache_data.get("data", cache_data)
        if isinstance(cd, dict):
            latencies = cd.get("latencies", {})

            # G4 should NOT have a large L3/L4 present.
            if profile.require_no_large_l3:
                for big_level in ("4096KB", "16384KB"):
                    if big_level in latencies:
                        entry = latencies[big_level]
                        if isinstance(entry, dict) and "error" not in entry:
                            return False, (
                                f"unexpected_large_cache:{big_level},"
                                f"claimed_arch={arch_lower}"
                            )

            # Tone ratio validation.
            tone_ratios = cd.get("tone_ratios", [])
            if tone_ratios and len(tone_ratios) > 0:
                mean_tone = statistics.mean(tone_ratios)
                if mean_tone < profile.tone_ratio_min:
                    return False, (
                        f"tone_ratio_too_low:mean={mean_tone:.2f},"
                        f"min={profile.tone_ratio_min},"
                        f"claimed_arch={arch_lower}"
                    )
                if mean_tone > profile.tone_ratio_max:
                    return False, (
                        f"tone_ratio_too_high:mean={mean_tone:.2f},"
                        f"max={profile.tone_ratio_max},"
                        f"claimed_arch={arch_lower}"
                    )

    return True, "cache_timing_ok"


# ---------------------------------------------------------------------------
# 4. Server-side bucket classification from verified features
# ---------------------------------------------------------------------------

@dataclass
class BucketClassification:
    """Result of server-side bucket classification."""
    bucket: str            # The verified reward bucket name
    multiplier: float      # The multiplier to apply
    claimed_arch: str      # What the miner originally claimed
    verified_arch: str     # What the server determined from evidence
    downgraded: bool       # True if the miner was moved to a lower bucket
    rejection_reasons: List[str] = field(default_factory=list)
    accepted: bool = True  # False = attestation fully rejected


# Base multipliers (mirrors ANTIQUITY_MULTIPLIERS in rip_200_round_robin).
_BUCKET_MULTIPLIERS: Dict[str, float] = {
    "vintage_powerpc_g4": 2.5,
    "vintage_powerpc_g5": 2.0,
    "vintage_powerpc_g3": 2.5,
    "vintage_68k":        3.0,
    "vintage_x86":        2.0,
    "retro_x86":          1.5,
    "power8":             1.8,
    "sparc":              2.0,
    "apple_silicon":      1.0,
    "arm64":              1.0,
    "modern_x86":         1.0,
    "unknown":            1.0,
}


def _infer_arch_from_features(
    simd_data: Dict[str, Any],
    cache_data: Dict[str, Any],
    cpu_brand: str,
) -> str:
    """Infer the most likely architecture bucket from raw hardware evidence.

    This is the server-side replacement for trusting ``device_arch``.
    """
    data = {}
    if simd_data and isinstance(simd_data, dict):
        data = simd_data.get("data", simd_data)
        if not isinstance(data, dict):
            data = simd_data

    has_altivec = bool(data.get("has_altivec", False))
    has_sse2 = bool(data.get("has_sse2", False))
    has_avx = bool(data.get("has_avx", False))
    has_neon = bool(data.get("has_neon", False))

    # Modern x86 is the most common -- check first.
    if has_sse2 or has_avx or _brand_looks_modern_x86(cpu_brand):
        return "modern_x86"

    if has_neon:
        brand_lower = (cpu_brand or "").lower()
        if "apple" in brand_lower:
            return "apple_silicon"
        return "arm64"

    if has_altivec:
        # Could be G4, G5, or Power8.
        brand_lower = (cpu_brand or "").lower()
        if "ibm" in brand_lower or "power8" in brand_lower or "power9" in brand_lower:
            return "power8"
        # Distinguish G4 vs G5 by cache structure if possible.
        if cache_data and isinstance(cache_data, dict):
            cd = cache_data.get("data", cache_data)
            if isinstance(cd, dict):
                latencies = cd.get("latencies", {})
                if "4096KB" in latencies:
                    return "vintage_powerpc_g5"
        return "vintage_powerpc_g4"

    # No SIMD at all -- likely very old.
    brand_lower = (cpu_brand or "").lower()
    if any(kw in brand_lower for kw in ("motorola", "68k", "mc68")):
        return "vintage_68k"
    if any(kw in brand_lower for kw in ("powerpc", "ppc", "power macintosh")):
        return "vintage_powerpc_g3"

    return "modern_x86"  # conservative default


def classify_reward_bucket(
    claimed_arch: str,
    cpu_brand: str,
    fingerprint: Dict[str, Any],
) -> BucketClassification:
    """Server-side reward-bucket classification.

    Instead of trusting the client-supplied ``device_arch`` directly, this
    function:

    1. Runs brand-string cross-validation.
    2. Checks SIMD evidence.
    3. Checks cache-timing profile.
    4. Infers the *actual* architecture from verified features.
    5. Assigns the miner to the correct reward bucket and multiplier.

    If the miner's claim is inconsistent, they are downgraded to the
    bucket their evidence supports (usually ``modern_x86`` at 1.0x).
    """
    reasons: List[str] = []

    # ---- Extract fingerprint sub-sections ----
    checks = fingerprint.get("checks", {}) if isinstance(fingerprint, dict) else {}
    if not checks and isinstance(fingerprint, dict):
        checks = {k: v for k, v in fingerprint.items()
                  if k in ("clock_drift", "cache_timing", "simd_identity",
                           "thermal_drift")}
    simd_data = checks.get("simd_identity", {})
    cache_data = checks.get("cache_timing", {})
    clock_data = checks.get("clock_drift", {})

    # ---- Step 1: Brand cross-validation ----
    brand_ok, brand_reason = validate_cpu_brand_vs_arch(cpu_brand, claimed_arch)
    if not brand_ok:
        reasons.append(brand_reason)

    # ---- Step 2: SIMD evidence ----
    simd_ok, simd_reason = validate_simd_evidence(claimed_arch, simd_data)
    if not simd_ok:
        reasons.append(simd_reason)

    # ---- Step 3: Cache-timing profile ----
    cache_ok, cache_reason = validate_cache_timing(
        claimed_arch, cache_data, clock_data,
    )
    if not cache_ok:
        reasons.append(cache_reason)

    # ---- Step 4: Server-side feature inference ----
    verified_arch = _infer_arch_from_features(simd_data, cache_data, cpu_brand)

    # ---- Step 5: Determine bucket ----
    all_checks_passed = brand_ok and simd_ok and cache_ok

    if all_checks_passed:
        # Trust the claim -- it is consistent with evidence.
        bucket = _arch_to_bucket(claimed_arch)
        multiplier = _BUCKET_MULTIPLIERS.get(bucket, 1.0)
        return BucketClassification(
            bucket=bucket,
            multiplier=multiplier,
            claimed_arch=claimed_arch,
            verified_arch=verified_arch,
            downgraded=False,
        )

    # Downgrade: use the server-inferred architecture instead.
    bucket = verified_arch  # already a bucket name
    multiplier = _BUCKET_MULTIPLIERS.get(bucket, 1.0)

    return BucketClassification(
        bucket=bucket,
        multiplier=multiplier,
        claimed_arch=claimed_arch,
        verified_arch=verified_arch,
        downgraded=True,
        rejection_reasons=reasons,
        accepted=True,  # still accepted, but at lower multiplier
    )


def _arch_to_bucket(arch: str) -> str:
    """Map a claimed device_arch to a canonical bucket name."""
    arch_lower = (arch or "").lower().strip()
    mapping = {
        "g4": "vintage_powerpc_g4",
        "g5": "vintage_powerpc_g5",
        "g3": "vintage_powerpc_g3",
        "powerpc": "vintage_powerpc_g3",
        "ppc": "vintage_powerpc_g3",
        "power macintosh": "vintage_powerpc_g4",
        "power8": "power8",
        "power9": "power8",
        "68k": "vintage_68k",
        "m68k": "vintage_68k",
        "amiga_68k": "vintage_68k",
        "sparc": "sparc",
        "apple_silicon": "apple_silicon",
        "arm64": "arm64",
        "aarch64": "arm64",
        "modern_x86": "modern_x86",
        "x86_64": "modern_x86",
        "x86-64": "modern_x86",
        "amd64": "modern_x86",
        "retro_x86": "retro_x86",
        "vintage_x86": "vintage_x86",
    }
    return mapping.get(arch_lower, "modern_x86")


# ---------------------------------------------------------------------------
# 5. Database helpers (sqlite3, following Rustchain patterns)
# ---------------------------------------------------------------------------

def log_bucket_classification(
    db: sqlite3.Connection,
    miner_id: str,
    classification: BucketClassification,
    ts: Optional[int] = None,
) -> None:
    """Write a bucket-classification audit row.

    Table ``rip201_bucket_audit`` is created if it does not exist.
    """
    ts = ts or int(time.time())
    db.execute("""
        CREATE TABLE IF NOT EXISTS rip201_bucket_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          INTEGER NOT NULL,
            miner       TEXT    NOT NULL,
            claimed_arch TEXT,
            verified_arch TEXT,
            bucket      TEXT,
            multiplier  REAL,
            downgraded  INTEGER,
            reasons     TEXT
        )
    """)
    db.execute("""
        INSERT INTO rip201_bucket_audit
            (ts, miner, claimed_arch, verified_arch, bucket, multiplier, downgraded, reasons)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ts,
        miner_id,
        classification.claimed_arch,
        classification.verified_arch,
        classification.bucket,
        classification.multiplier,
        int(classification.downgraded),
        "|".join(classification.rejection_reasons),
    ))
    db.commit()


# ---------------------------------------------------------------------------
# 6. Integration helper -- drop-in for rewards_implementation_rip200.py
# ---------------------------------------------------------------------------

def get_verified_multiplier(
    miner_id: str,
    claimed_arch: str,
    cpu_brand: str,
    fingerprint: Dict[str, Any],
    chain_age_years: float,
    db: Optional[sqlite3.Connection] = None,
) -> float:
    """Return the time-aged multiplier using server-verified bucket.

    This is the function that ``rewards_implementation_rip200.py`` should
    call in place of the current
    ``get_time_aged_multiplier(device_arch, chain_age_years)`` to close
    the RIP-201 spoofing vector.
    """
    classification = classify_reward_bucket(
        claimed_arch, cpu_brand, fingerprint,
    )

    if db is not None:
        try:
            log_bucket_classification(db, miner_id, classification)
        except Exception:
            pass  # audit logging should never block reward calculation

    base = classification.multiplier

    # Apply time-aging decay (same formula as rip_200_round_robin).
    if base <= 1.0:
        return 1.0

    DECAY_RATE = 0.06  # mirrors rip_200_round_robin_1cpu1vote.py
    vintage_bonus = base - 1.0
    aged_bonus = max(0.0, vintage_bonus * (1 - DECAY_RATE * chain_age_years))

    return 1.0 + aged_bonus
