import unittest
import os
import time
from governance_engine import GovernanceEngine

class TestGovernance(unittest.TestCase):
    def setUp(self):
        # 使用內存數據庫進行快速測試
        self.db_path = "test_governance.db"
        self.engine = GovernanceEngine(self.db_path)

    def tearDown(self):
        # 清理測試數據庫
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_proposal_lifecycle(self):
        # 1. 測試 stake 不足
        ok, msg = self.engine.submit_proposal("user1", "Title", "Desc", 5.0)
        self.assertFalse(ok)
        self.assertIn("Insufficient RTC", msg)

        # 2. 測試成功提交
        ok, msg = self.engine.submit_proposal("user1", "Title", "Desc", 10.0)
        self.assertTrue(ok)
        
        # 3. 驗證狀態
        status = self.engine.get_proposal_status(1)
        self.assertIsNotNone(status['proposal'])
        self.assertEqual(status['proposal'][5], 'ACTIVE') # status column

    def test_weighted_voting(self):
        # 建立提案
        self.engine.submit_proposal("admin", "Vote Test", "Desc", 100.0)
        
        # G4 投票 (應為 2.5x)
        ok, msg = self.engine.cast_weighted_vote(1, "miner_g4", "g4", "YES", "sig1")
        self.assertTrue(ok)
        self.assertIn("2.5x", msg)

        # 386 投票 (應為 3.0x)
        ok, msg = self.engine.cast_weighted_vote(1, "miner_386", "386", "NO", "sig2")
        self.assertTrue(ok)
        self.assertIn("3.0x", msg)

        # Modern 投票 (應為 1.0x)
        ok, msg = self.engine.cast_weighted_vote(1, "miner_pc", "modern", "YES", "sig3")
        self.assertTrue(ok)

        # 驗證總票數
        status = self.engine.get_proposal_status(1)
        tally = status['tally']
        self.assertEqual(tally.get('YES', 0), 3.5) # 2.5 + 1.0
        self.assertEqual(tally.get('NO', 0), 3.0)  # 3.0

    def test_double_voting(self):
        self.engine.submit_proposal("admin", "Double Vote", "Desc", 100.0)
        self.engine.cast_weighted_vote(1, "spammer", "g4", "YES", "sig1")
        
        # 重複投票應失敗
        ok, msg = self.engine.cast_weighted_vote(1, "spammer", "g4", "NO", "sig2")
        self.assertFalse(ok)
        self.assertIn("Already voted", msg)

if __name__ == '__main__':
    unittest.main()
