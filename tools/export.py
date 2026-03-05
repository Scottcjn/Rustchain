#!/usr/bin/env python3
"""
RustChain Attestation Data Export Tool

Export attestation data to CSV, JSON, or Parquet formats.

Usage:
    python export.py --format csv --output data.csv
    python export.py --format json --output data.json
    python export.py --format parquet --output data.parquet
"""

import argparse
import json
import csv
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

DEFAULT_NODE_URL = "https://50.28.86.131"


class RustChainExporter:
    """Export RustChain attestation data"""
    
    def __init__(self, node_url: str = DEFAULT_NODE_URL):
        self.node_url = node_url.rstrip("/")
        import ssl
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
    
    def _fetch(self, endpoint: str) -> Any:
        """Fetch data from node API"""
        import urllib.request
        url = f"{self.node_url}{endpoint}"
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, context=self.ctx, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    
    def get_miners(self) -> List[Dict]:
        """Get all miners data"""
        return self._fetch("/api/miners")
    
    def get_epoch(self) -> Dict:
        """Get current epoch info"""
        return self._fetch("/epoch")
    
    def get_health(self) -> Dict:
        """Get node health"""
        return self._fetch("/health")
    
    def export_csv(self, miners: List[Dict], output: str):
        """Export to CSV"""
        if not miners:
            print("No data to export")
            return
        
        fieldnames = list(miners[0].keys())
        
        with open(output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(miners)
        
        print(f"Exported {len(miners)} records to {output}")
    
    def export_json(self, data: Any, output: str):
        """Export to JSON"""
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported to {output}")
    
    def export_parquet(self, miners: List[Dict], output: str):
        """Export to Parquet"""
        if not HAS_PANDAS:
            print("Error: pandas is required for Parquet export")
            print("Install with: pip install pandas pyarrow")
            sys.exit(1)
        
        if not miners:
            print("No data to export")
            return
        
        df = pd.DataFrame(miners)
        df.to_parquet(output, index=False)
        
        print(f"Exported {len(miners)} records to {output}")
    
    def export(self, format: str, output: str, include_epoch: bool = False):
        """Export data in specified format"""
        miners = self.get_miners()
        
        format = format.lower()
        
        if format == 'csv':
            self.export_csv(miners, output)
        elif format == 'json':
            data = {"miners": miners}
            if include_epoch:
                data["epoch"] = self.get_epoch()
                data["health"] = self.get_health()
            self.export_json(data, output)
        elif format == 'parquet':
            self.export_parquet(miners, output)
        else:
            print(f"Unknown format: {format}")
            print("Supported formats: csv, json, parquet")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Attestation Data Export Tool"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json", "parquet"],
        default="json",
        help="Export format (default: json)"
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file path"
    )
    parser.add_argument(
        "--node-url",
        default=DEFAULT_NODE_URL,
        help="RustChain node URL"
    )
    parser.add_argument(
        "--include-epoch",
        action="store_true",
        help="Include epoch and health info in JSON export"
    )
    
    args = parser.parse_args()
    
    exporter = RustChainExporter(args.node_url)
    exporter.export(args.format, args.output, args.include_epoch)


if __name__ == "__main__":
    main()
