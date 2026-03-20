// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Fuzz runner configuration
FUZZ_DB_PATH = "fuzz_results.db"
CORPUS_DIR = "fuzz_corpus"
CRASH_DIR = "crash_corpus"
REPORTS_DIR = "fuzz_reports"

class AttestationFuzzRunner:
    def __init__(self, db_path: str = FUZZ_DB_PATH):
        self.db_path = db_path
        self.setup_directories()
        self.init_database()

    def setup_directories(self):
        """Ensure required directories exist"""
        for directory in [CORPUS_DIR, CRASH_DIR, REPORTS_DIR]:
            os.makedirs(directory, exist_ok=True)

    def init_database(self):
        """Initialize fuzz results tracking database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS fuzz_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    total_cases INTEGER DEFAULT 0,
                    crash_count INTEGER DEFAULT 0,
                    timeout_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    config TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS crash_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    crash_hash TEXT UNIQUE,
                    payload_size INTEGER,
                    exception_type TEXT,
                    crash_info TEXT,
                    input_file TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def generate_campaign_id(self) -> str:
        """Generate unique campaign identifier"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"attest_fuzz_{timestamp}"

    def run_basic_campaign(self, iterations: int = 1000, timeout: int = 30) -> Dict[str, Any]:
        """Execute basic fuzz campaign with configurable parameters"""
        campaign_id = self.generate_campaign_id()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO fuzz_runs (campaign_id, run_type, config) VALUES (?, ?, ?)",
                (campaign_id, "basic", json.dumps({"iterations": iterations, "timeout": timeout}))
            )
            conn.commit()

        results = {
            "campaign_id": campaign_id,
            "total_cases": 0,
            "crashes": 0,
            "timeouts": 0,
            "start_time": time.time()
        }

        # Import fuzzing engine here to avoid circular imports
        try:
            from attestation_fuzz_engine import AttestationFuzzEngine
            fuzzer = AttestationFuzzEngine()
        except ImportError:
            logging.error("Fuzz engine not available - install dependencies first")
            return {"error": "Missing fuzz engine"}

        logging.info(f"Starting basic campaign {campaign_id} with {iterations} iterations")

        for i in range(iterations):
            try:
                # Generate and test malformed attestation
                test_case = fuzzer.generate_malformed_attestation()
                result = fuzzer.test_attestation_payload(test_case, timeout_sec=timeout)

                results["total_cases"] += 1

                if result.get("crashed"):
                    results["crashes"] += 1
                    self.save_crash_case(campaign_id, test_case, result)

                if result.get("timeout"):
                    results["timeouts"] += 1

                if i % 100 == 0:
                    logging.info(f"Processed {i}/{iterations} cases")

            except Exception as e:
                logging.error(f"Error in fuzz case {i}: {e}")
                continue

        results["duration"] = time.time() - results["start_time"]
        self.finalize_campaign(campaign_id, results)

        return results

    def run_regression_campaign(self, corpus_dir: str = CRASH_DIR) -> Dict[str, Any]:
        """Run regression testing against known crash corpus"""
        campaign_id = self.generate_campaign_id()

        crash_files = list(Path(corpus_dir).glob("*.json"))
        if not crash_files:
            return {"error": "No crash corpus files found", "corpus_dir": corpus_dir}

        results = {
            "campaign_id": campaign_id,
            "regression_cases": len(crash_files),
            "regressions": 0,
            "fixed": 0
        }

        logging.info(f"Starting regression campaign {campaign_id} with {len(crash_files)} test cases")

        try:
            from attestation_fuzz_engine import AttestationFuzzEngine
            fuzzer = AttestationFuzzEngine()
        except ImportError:
            return {"error": "Fuzz engine not available"}

        for crash_file in crash_files:
            try:
                with open(crash_file, 'r') as f:
                    test_data = json.load(f)

                result = fuzzer.test_attestation_payload(test_data.get("payload", {}))

                if result.get("crashed"):
                    results["regressions"] += 1
                    logging.warning(f"Regression detected: {crash_file.name}")
                else:
                    results["fixed"] += 1

            except Exception as e:
                logging.error(f"Error testing regression case {crash_file}: {e}")

        return results

    def run_continuous_campaign(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """Run time-bounded continuous fuzzing campaign"""
        campaign_id = self.generate_campaign_id()
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        results = {
            "campaign_id": campaign_id,
            "duration_minutes": duration_minutes,
            "total_cases": 0,
            "crashes": 0,
            "unique_crashes": 0
        }

        logging.info(f"Starting continuous campaign {campaign_id} for {duration_minutes} minutes")

        try:
            from attestation_fuzz_engine import AttestationFuzzEngine
            fuzzer = AttestationFuzzEngine()
        except ImportError:
            return {"error": "Fuzz engine not available"}

        crash_hashes = set()

        while time.time() < end_time:
            try:
                test_case = fuzzer.generate_malformed_attestation()
                result = fuzzer.test_attestation_payload(test_case)

                results["total_cases"] += 1

                if result.get("crashed"):
                    results["crashes"] += 1
                    crash_hash = result.get("crash_hash")

                    if crash_hash and crash_hash not in crash_hashes:
                        crash_hashes.add(crash_hash)
                        results["unique_crashes"] += 1
                        self.save_crash_case(campaign_id, test_case, result)

                if results["total_cases"] % 1000 == 0:
                    elapsed = (time.time() - start_time) / 60
                    logging.info(f"Processed {results['total_cases']} cases in {elapsed:.1f} minutes")

            except KeyboardInterrupt:
                logging.info("Campaign interrupted by user")
                break
            except Exception as e:
                logging.error(f"Error during continuous fuzzing: {e}")

        results["actual_duration"] = (time.time() - start_time) / 60
        return results

    def save_crash_case(self, campaign_id: str, payload: Dict[str, Any], result: Dict[str, Any]):
        """Save crashing test case to corpus and database"""
        crash_hash = result.get("crash_hash", "unknown")

        # Save to filesystem
        crash_filename = f"crash_{crash_hash}_{int(time.time())}.json"
        crash_path = os.path.join(CRASH_DIR, crash_filename)

        crash_data = {
            "campaign_id": campaign_id,
            "payload": payload,
            "crash_info": result.get("exception_info", ""),
            "discovered_at": datetime.now().isoformat(),
            "crash_hash": crash_hash
        }

        with open(crash_path, 'w') as f:
            json.dump(crash_data, f, indent=2)

        # Save to database
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT INTO crash_entries
                    (campaign_id, crash_hash, payload_size, exception_type, crash_info, input_file)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    campaign_id,
                    crash_hash,
                    len(json.dumps(payload)),
                    result.get("exception_type", "unknown"),
                    result.get("exception_info", ""),
                    crash_filename
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                # Duplicate crash hash, skip
                pass

    def finalize_campaign(self, campaign_id: str, results: Dict[str, Any]):
        """Update campaign completion status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE fuzz_runs
                SET end_time = CURRENT_TIMESTAMP,
                    total_cases = ?,
                    crash_count = ?,
                    timeout_count = ?,
                    status = 'completed'
                WHERE campaign_id = ?
            ''', (
                results.get("total_cases", 0),
                results.get("crashes", 0),
                results.get("timeouts", 0),
                campaign_id
            ))
            conn.commit()

    def generate_report(self, campaign_id: Optional[str] = None) -> str:
        """Generate campaign report"""
        report_filename = f"fuzz_report_{campaign_id or 'summary'}_{int(time.time())}.json"
        report_path = os.path.join(REPORTS_DIR, report_filename)

        with sqlite3.connect(self.db_path) as conn:
            if campaign_id:
                # Single campaign report
                run_data = conn.execute(
                    "SELECT * FROM fuzz_runs WHERE campaign_id = ?", (campaign_id,)
                ).fetchone()

                crashes = conn.execute(
                    "SELECT * FROM crash_entries WHERE campaign_id = ?", (campaign_id,)
                ).fetchall()
            else:
                # Summary report
                run_data = conn.execute("SELECT * FROM fuzz_runs ORDER BY start_time DESC").fetchall()
                crashes = conn.execute("SELECT * FROM crash_entries ORDER BY discovered_at DESC").fetchall()

        report = {
            "generated_at": datetime.now().isoformat(),
            "campaign_id": campaign_id,
            "runs": run_data,
            "crashes": crashes,
            "summary": {
                "total_runs": len(run_data) if isinstance(run_data, list) else 1,
                "total_crashes": len(crashes),
                "corpus_size": len(list(Path(CRASH_DIR).glob("*.json")))
            }
        }

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logging.info(f"Report generated: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description="Attestation Fuzz Campaign Runner")
    parser.add_argument("--mode", choices=["basic", "regression", "continuous"],
                       default="basic", help="Campaign execution mode")
    parser.add_argument("--iterations", type=int, default=1000,
                       help="Number of test cases for basic mode")
    parser.add_argument("--duration", type=int, default=60,
                       help="Duration in minutes for continuous mode")
    parser.add_argument("--timeout", type=int, default=30,
                       help="Timeout per test case in seconds")
    parser.add_argument("--corpus-dir", default=CRASH_DIR,
                       help="Directory containing crash corpus for regression testing")
    parser.add_argument("--report-only", action="store_true",
                       help="Generate report without running campaign")
    parser.add_argument("--campaign-id", help="Specific campaign ID for reporting")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('fuzz_runner.log')
        ]
    )

    runner = AttestationFuzzRunner()

    if args.report_only:
        report_path = runner.generate_report(args.campaign_id)
        print(f"Report generated: {report_path}")
        return 0

    # Execute campaign based on mode
    if args.mode == "basic":
        results = runner.run_basic_campaign(args.iterations, args.timeout)
    elif args.mode == "regression":
        results = runner.run_regression_campaign(args.corpus_dir)
    elif args.mode == "continuous":
        results = runner.run_continuous_campaign(args.duration)

    if "error" in results:
        print(f"Campaign failed: {results['error']}")
        return 1

    # Generate completion report
    if "campaign_id" in results:
        report_path = runner.generate_report(results["campaign_id"])
        print(f"Campaign completed. Report: {report_path}")

        # Print summary
        print(f"Campaign ID: {results['campaign_id']}")
        print(f"Total cases: {results.get('total_cases', 'N/A')}")
        print(f"Crashes found: {results.get('crashes', results.get('regressions', 'N/A'))}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
