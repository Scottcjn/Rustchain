import socket
import threading
import json
import requests

LISTEN_PORT = 8585
FORWARD_URL = "http://127.0.0.1:5000/validate"  # Your PoA REST API

def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    try:
        data = conn.recv(2048).decode().strip()
        print(f"[>] Received data: {data}")

        # Try to parse and forward JSON if valid
        try:
            payload = json.loads(data)
            print("[~] Parsed JSON:")
            print(json.dumps(payload, indent=2))

            r = requests.post(FORWARD_URL, json=payload)
            print(f"[✓] Forwarded to REST API. Status: {r.status_code}")
            conn.sendall(f"PoA received. Status: {r.status_code}\n".encode())
        except json.JSONDecodeError:
            print("[!] Invalid JSON. Ignoring.")
            conn.sendall(b"Invalid JSON format.\n")

    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        conn.close()
        print(f"[-] Connection from {addr} closed.")

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(('', LISTEN_PORT))
        server.listen(5)
        print(f"[🔌] RustChain TCP Listener active on port {LISTEN_PORT}...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr)).start()

if __name__ == "__main__":
    start_server()
