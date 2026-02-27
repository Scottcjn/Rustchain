#!/usr/bin/env python3
from bridge.ergo.daemon import BridgeDaemon

if __name__ == "__main__":
    d = BridgeDaemon(dry_run=True)
    print(d.run_once())
