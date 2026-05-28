#!/usr/bin/env python3
"""Surgical fix for Node 1's calculate_epoch_rewards_time_aged.

Bug: function queries miner_attest_recent.ts_ok within epoch window. Miners
whose attestation timestamp crossed the epoch boundary (enrolled in epoch N
but attested in epoch N+1) get dropped. T40 enrolled at epoch 175 weight 1.9
but attested 71s after epoch end -> NOT paid.

Fix: prefer epoch_enroll snapshot (canonical per-epoch weights). Fall back to
the old time-window query only if epoch_enroll has no rows.

Surgical: only changes the body of calculate_epoch_rewards_time_aged. Uses
only helpers already present on Node 1 (no new deps).
"""
import argparse, py_compile, shutil, sys, time
from pathlib import Path

SRV_FILE = Path("/root/rustchain/rip_200_round_robin_1cpu1vote.py")

OLD_FUNC_HEAD = '''def calculate_epoch_rewards_time_aged(
    db_path: str,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int
) -> Dict[str, int]:'''

# Sentinel that's unique to OLD function: queries miner_attest_recent by ts_ok
# directly without checking epoch_enroll first.
OLD_SENTINEL = '''        # Get unique attested miners during epoch (any attestation in epoch window)
        cursor.execute("""
            SELECT DISTINCT miner, device_arch, COALESCE(fingerprint_passed, 1) as fp
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
        """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))

        epoch_miners = cursor.fetchall()'''

NEW_SENTINEL = '''        # FIX (settlement-integrity): Prefer epoch_enroll (per-epoch snapshot,
        # canonical weight). Fall back to the legacy time-window query only when
        # epoch_enroll has no rows for the epoch.
        #
        # Without this, miners whose attestation timestamp crossed the epoch
        # boundary (e.g. enrolled at slot N-1, attested at slot N+1) get dropped
        # by the ts_ok BETWEEN window — even though they enrolled correctly.
        # Verified case: t40-thinkpad-banias enrolled at epoch 175 with
        # weight 1.9 but attested 71s after epoch_end_ts of 175.
        try:
            cursor.execute(
                "SELECT 1 FROM epoch_enroll WHERE epoch = ? LIMIT 1", (epoch,)
            )
            has_enroll = cursor.fetchone() is not None
        except sqlite3.Error:
            has_enroll = False

        if has_enroll:
            # Canonical path: use enrolled list + their snapshot weights.
            cursor.execute(
                "SELECT ee.miner_pk, "
                "       COALESCE(mar.device_arch, 'unknown'), "
                "       COALESCE(mar.fingerprint_passed, 1), "
                "       ee.weight "
                "FROM epoch_enroll ee "
                "LEFT JOIN miner_attest_recent mar ON ee.miner_pk = mar.miner "
                "WHERE ee.epoch = ?",
                (epoch,)
            )
            enrolled_rows = cursor.fetchall()
            epoch_miners = [(m, arch, fp) for (m, arch, fp, _w) in enrolled_rows]
            enrolled_weights = {m: float(w) for (m, _a, _f, w) in enrolled_rows}
        else:
            # Legacy fallback (kept for backward-compat with epochs that
            # never wrote enrollment rows).
            cursor.execute("""
                SELECT DISTINCT miner, device_arch, COALESCE(fingerprint_passed, 1) as fp
                FROM miner_attest_recent
                WHERE ts_ok >= ? AND ts_ok <= ?
            """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))
            epoch_miners = cursor.fetchall()
            enrolled_weights = {}'''

# Also rewrite the per-miner weight assignment to honor enrolled_weights.
OLD_WEIGHT_ASSIGN = '''        # STRICT: VMs/emulators with failed fingerprint get ZERO weight
        if fingerprint_ok == 0:
            weight = 0.0  # No rewards for failed fingerprint
            print(f"[REWARD] {miner_id[:20]}... fingerprint=FAIL -> weight=0")
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)'''

NEW_WEIGHT_ASSIGN = '''        # STRICT: VMs/emulators with failed fingerprint get ZERO weight
        if fingerprint_ok == 0:
            weight = 0.0  # No rewards for failed fingerprint
            print(f"[REWARD] {miner_id[:20]}... fingerprint=FAIL -> weight=0")
        elif miner_id in enrolled_weights:
            # FIX: honor the per-epoch enrollment weight snapshot. This is the
            # weight the miner committed to at enrollment time and matches
            # what /api/miners and other endpoints report.
            weight = enrolled_weights[miner_id]
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)'''


def patch_file(path, dry_run):
    text = path.read_text()
    if "enrolled_weights" in text and "Prefer epoch_enroll" in text:
        return "ALREADY PATCHED (enrolled_weights logic present)"
    if OLD_FUNC_HEAD not in text:
        return "ERROR: function signature anchor not found"
    if OLD_SENTINEL not in text:
        return "ERROR: old miner-attest-recent query anchor not found"
    if OLD_WEIGHT_ASSIGN not in text:
        return "ERROR: weight-assignment anchor not found"

    new_text = text.replace(OLD_SENTINEL, NEW_SENTINEL, 1)
    new_text = new_text.replace(OLD_WEIGHT_ASSIGN, NEW_WEIGHT_ASSIGN, 1)

    if new_text == text:
        return "ERROR: replacements produced no change"
    if dry_run:
        return f"DRY-RUN: would add {len(new_text) - len(text)} bytes"

    bk = path.with_name(f"{path.name}.bak-settle-fix-{int(time.time())}")
    shutil.copy(path, bk)
    path.write_text(new_text)
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copy(bk, path)
        return f"ERROR: syntax broke, reverted — {e}"
    return f"PATCHED ({len(new_text) - len(text)} bytes added) — backup: {bk.name}"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--base", default="/root/rustchain")
    args = p.parse_args()
    SRV_FILE = Path(args.base) / "rip_200_round_robin_1cpu1vote.py"
    if not SRV_FILE.exists():
        print(f"FATAL: {SRV_FILE} not found", file=sys.stderr)
        sys.exit(2)
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print(f"File: {SRV_FILE}")
    print(f"  {patch_file(SRV_FILE, args.dry_run)}")
