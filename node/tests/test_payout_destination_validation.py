# SPDX-License-Identifier: MIT
"""A payout destination must be spendable, or the transfer is a burn.

/wallet/transfer accepted ANY non-empty string as `to_miner`. An audit on
2026-09-20 found 22 accounts whose ids start with "RTC" but are not canonical
addresses, holding ~906 RTC between them -- roughly 520 of it real contributor
bounty money. Nothing can ever sign for those ids, so the RTC is burned while the
ledger records a successful payout; the books looked healthy the whole time.

The addresses in ``STRANDED`` are the real ones, copied from production. They are
the regression corpus: if any of them is ever accepted again, this test fails.
"""
import unittest

try:
    from payout_preflight import validate_wallet_transfer_admin
except ImportError:
    from node.payout_preflight import validate_wallet_transfer_admin


# Verified on node1 2026-09-20. Balance in RTC, for the record.
STRANDED = [
    ("RTC64aa3fc417e75224e1574acae906f", 250.00),               # short hex (32)
    ("RTC-agent-antigravity-9944", 207.00),                     # free-text id
    ("RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f3", 144.00),     # one char short (42)
    ("RTCdos8086test1234567890abcdef12345678", 93.97),          # test miner id
    ("RTC1274aea37cc74eb889bf2abfd22fee274fc37706b", 90.00),    # one char long (44)
    ("RTC14241718572ec3bd1c0c4ee26ed2fc4bf6fca15", 25.00),
    ("RTCfe13452d122263caf633ab1876bd9631133b68b", 20.00),
    ("RTC4325af95d26d59c3ef025963656d22af", 17.00),
    ("RTC29WwMjwcaFeTTQqKaMNmFUFLYz3f", 10.00),                 # a Solana address
    ("RTC-agent-fino31415-d969", 10.00),
    ("RTCe91ababe9fe345ce7c03d2ebeef566b7e182", 8.00),
    ("RTCrebel117bountywallet0000000000000000001", 6.00),
    ("RTCf15172ce23e20efaa390edc0ef12b7ef5", 5.50),
    ("RTC17c0d21f04f6f65c1a85c0aeb5d4a305d57531096", 5.00),
    ("RTC1a6281b7220b7a4925a462b51379cd36da6d84f", 5.00),
    ("RTC", 5.00),                                              # account literally "RTC"
    ("RTC03e097b44dd94726a5c3dc7d94892425", 0.50),
    ("RTC-SECURITY-RESEARCH-POC-rix-nofunds-000000000000000000", 0.50),
    ("RTC78f1fa6b385000000000000000000000000000", 0.000001),
]

VALID_ADDRESS = "RTC1d48d848a5aa5ecf2c5f01aa5fb64837daaf2f35"   # canonical, 43 chars

# Non-address account ids that hold real balances and MUST keep working.
# 1,113 such accounts held 382,257 RTC on 2026-09-20.
HANDLE_DESTINATIONS = [
    "xxzzzzy",
    "founder_community",
    "founder_team_bounty",
    "dual-g4-125",
    "ProgLover15",
    "Vyacheslav-Tomashevskiy",
    "bottube_platform",
    "airdrop_pool",
    # RTC as a *suffix* is a real node-reward account shape, not an address.
    "9fd582ec147e58c241de383b20bff8ca4650be6bRTC",
]


def _payload(to_miner):
    return {"from_miner": "founder_community", "to_miner": to_miner, "amount_rtc": 1}


class StrandedDestinationsAreRejected(unittest.TestCase):
    def test_every_real_stranded_address_is_refused(self):
        for addr, balance in STRANDED:
            with self.subTest(address=addr, stranded_rtc=balance):
                r = validate_wallet_transfer_admin(_payload(addr))
                self.assertFalse(r.ok, f"{addr} accepted; {balance} RTC would burn again")
                self.assertEqual(r.error, "invalid_destination_address")

    def test_rejection_explains_both_valid_shapes(self):
        r = validate_wallet_transfer_admin(_payload("RTC-agent-frog"))
        self.assertFalse(r.ok)
        self.assertIn("40 lowercase hex", r.details.get("hint", ""))
        self.assertEqual(r.details.get("to_miner"), "RTC-agent-frog")

    def test_mixed_case_is_refused(self):
        """The surim0n case: uppercase hex derives from no key, so it is unspendable."""
        r = validate_wallet_transfer_admin(_payload(VALID_ADDRESS.upper()))
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "invalid_destination_address")
        mixed = "RTC5800896ed658AA511D029361b6D7388dDB29248B"
        self.assertFalse(validate_wallet_transfer_admin(_payload(mixed)).ok)


class LegitimateDestinationsStillWork(unittest.TestCase):
    def test_canonical_address_accepted(self):
        r = validate_wallet_transfer_admin(_payload(VALID_ADDRESS))
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.details["to_miner"], VALID_ADDRESS)

    def test_handle_wallets_accepted(self):
        for handle in HANDLE_DESTINATIONS:
            with self.subTest(handle=handle):
                r = validate_wallet_transfer_admin(_payload(handle))
                self.assertTrue(r.ok, f"{handle} rejected ({r.error}); handle wallets hold real balances")


class SourceStaysPermissive(unittest.TestCase):
    """Sweeping funds OFF a broken address must remain possible.

    The check is deliberately asymmetric: guarding the destination stops new
    strandings, while leaving the source open is what let the 2026-09-20 merges
    recover 276.50 RTC from five truncated addresses.
    """

    def test_broken_source_to_good_destination_is_allowed(self):
        for addr, _ in STRANDED:
            with self.subTest(source=addr):
                r = validate_wallet_transfer_admin(
                    {"from_miner": addr, "to_miner": VALID_ADDRESS, "amount_rtc": 1}
                )
                self.assertTrue(r.ok, f"cannot sweep {addr}: {r.error}")

    def test_broken_source_to_broken_destination_still_refused(self):
        r = validate_wallet_transfer_admin(
            {"from_miner": "RTC-agent-frog", "to_miner": "RTC-agent-antigravity-9944", "amount_rtc": 1}
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "invalid_destination_address")


class ValidationOrderIsStable(unittest.TestCase):
    def test_destination_checked_before_amount(self):
        """A caller with two mistakes should hear about the unrecoverable one."""
        r = validate_wallet_transfer_admin(
            {"from_miner": "founder_community", "to_miner": "RTC", "amount_rtc": -5}
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "invalid_destination_address")

    def test_missing_destination_still_reports_missing(self):
        r = validate_wallet_transfer_admin({"from_miner": "a", "to_miner": "", "amount_rtc": 1})
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "missing_from_or_to")


if __name__ == "__main__":
    unittest.main()
