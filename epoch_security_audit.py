# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import json
from flask import Flask, render_template_string, jsonify, request
import logging
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = 'rustchain.db'
EPOCH_DURATION = 600  # 10 minutes

class EpochSecurityAudit:
    def __init__(self):
        self.test_results = []
        self.vulnerabilities_found = []
        self.audit_id = int(time.time())

    def log_result(self, test_name, passed, details, severity="LOW"):
        result = {
            'test_name': test_name,
            'passed': passed,
            'details': details,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        if not passed:
            self.vulnerabilities_found.append(result)

    def get_current_epoch(self):
        return int(time.time()) // EPOCH_DURATION

    def create_test_miner(self, node_id, hardware_class="A"):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO nodes (node_id, hardware_class, status, last_seen)
                VALUES (?, ?, 'active', ?)
            ''', (node_id, hardware_class, int(time.time())))
            conn.commit()

    def test_double_enrollment(self):
        """Test if miners can enroll in the same epoch twice"""
        test_node = f"test_double_{self.audit_id}"
        current_epoch = self.get_current_epoch()

        try:
            self.create_test_miner(test_node)

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # First enrollment
                cursor.execute('''
                    INSERT INTO epoch_enrollments (epoch_id, node_id, enrollment_time, hardware_mu
