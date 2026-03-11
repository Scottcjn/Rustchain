#!/usr/bin/env python3
"""RustChain Load Test Suite"""

import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8080"
CONCURRENT_USERS = 100

class LoadTest:
    def __init__(self):
        self.results = {'success': 0, 'failed': 0, 'times': []}
    
    def test_health(self):
        try:
            start = time.time()
            r = requests.get(f"{BASE_URL}/health", timeout=5)
            elapsed = time.time() - start
            if r.status_code == 200:
                self.results['success'] += 1
            else:
                self.results['failed'] += 1
            self.results['times'].append(elapsed)
        except:
            self.results['failed'] += 1
    
    def run(self, num_requests):
        with ThreadPoolExecutor(max_workers=CONCURRENT_USERS) as executor:
            futures = [executor.submit(self.test_health) for _ in range(num_requests)]
            list(futures)
        
        avg = sum(self.results['times']) / len(self.results['times']) if self.results['times'] else 0
        print(f"Success: {self.results['success']}, Failed: {self.results['failed']}")
        print(f"Avg time: {avg*1000:.1f}ms")

if __name__ == "__main__":
    test = LoadTest()
    test.run(100)

# Bounty wallet: RTC27a4b8256b4d3c63737b27e96b181223cc8774ae
