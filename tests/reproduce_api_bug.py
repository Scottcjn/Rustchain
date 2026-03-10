import urllib.request
import urllib.error
import sys

def reproduce_bug():
    """
    Automated reproduction script for the 500 Internal Server Error bug.
    Queries a non-existent block to verify error handling behavior.
    """
    url = "http://localhost:5000/api/chain/block/999999"
    print(f"[*] Attempting to fetch non-existent block from {url}")
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            print("[-] Unexpected success. The API returned 200 OK.")
            sys.exit(1)
    except urllib.error.HTTPError as e:
        if e.code == 500:
            print("[+] BUG SUCCESSFULLY REPRODUCED: Server returned 500 Internal Server Error.")
            print(f"[+] Response body: {e.read().decode('utf-8')}")
        elif e.code == 404:
            print("[-] BUG FIXED: Server correctly handled the missing block and returned 404 Not Found.")
        else:
            print(f"[-] Unexpected HTTP error code: {e.code}")

if __name__ == "__main__":
    reproduce_bug()
