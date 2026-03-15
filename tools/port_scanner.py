#!/usr/bin/env python3
"""RustChain Port Scanner — Check if required ports are open."""
import socket, sys, os
PORTS = {"API": 8088, "Dashboard": 8099, "Prometheus": 9100, "Grafana": 3000, "Nginx HTTP": 80, "Nginx HTTPS": 443}
def scan(host="localhost"):
    print(f"Port Scan: {host}")
    for name, port in PORTS.items():
        try:
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            print(f"  OPEN   {port:>5}  {name}")
        except:
            print(f"  CLOSED {port:>5}  {name}")
if __name__ == "__main__":
    scan(sys.argv[1] if len(sys.argv) > 1 else "localhost")
