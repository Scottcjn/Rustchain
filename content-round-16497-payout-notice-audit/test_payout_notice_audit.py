# SPDX-License-Identifier: MIT
import json
import unittest

from payout_notice_audit import audit_file, audit_notice


class PayoutNoticeAuditTests(unittest.TestCase):
    def test_authorized_complete_notice_requires_record_verification(self):
        result = audit_notice(
            {
                "author": "Scottcjn",
                "body": (
                    "amount: 33_RTC wallet: demo-wallet pending_id: pending-42 "
                    "tx_hash: tx-demo-abc confirms_at: 2026-09-02T12:00:00Z"
                ),
            }
        )

        self.assertEqual(result["status"], "ready_for_project_record_verification")
        self.assertIs(result["settled"], False)
        self.assertEqual(result["missing"], [])

    def test_unauthorized_notice_is_rejected_even_with_all_fields(self):
        result = audit_notice(
            {
                "author": "helpful-stranger",
                "body": (
                    "amount: 33_RTC wallet: demo-wallet pending_id: pending-42 "
                    "tx_hash: tx-demo-abc confirms_at: tomorrow"
                ),
            }
        )

        self.assertEqual(result["status"], "reject_unauthorized_author")
        self.assertIs(result["settled"], False)

    def test_authorized_login_match_is_case_insensitive(self):
        result = audit_notice(
            {
                "author": "SCOTTCJN",
                "body": (
                    "amount: 33_RTC wallet: demo-wallet pending_id: pending-42 "
                    "tx_hash: tx-demo-abc confirms_at: 2026-09-02T12:00:00Z"
                ),
            }
        )

        self.assertEqual(result["status"], "ready_for_project_record_verification")

    def test_authorized_notice_with_missing_fields_is_held(self):
        result = audit_notice({"author": "AutoJanitor", "body": "amount: 33_RTC"})

        self.assertEqual(result["status"], "hold_missing_fields")
        self.assertEqual(
            result["missing"], ["wallet", "pending_id", "tx_hash", "confirms_at"]
        )

    def test_file_input_must_be_an_array(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as directory:
            path = Path(directory) / "notice.json"
            path.write_text(json.dumps({"author": "Scottcjn"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON array"):
                audit_file(path)

    def test_each_file_item_must_be_an_object(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as directory:
            path = Path(directory) / "notice.json"
            path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "each notice"):
                audit_file(path)


if __name__ == "__main__":
    unittest.main()
