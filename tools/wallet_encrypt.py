#!/usr/bin/env python3
"""RustChain Wallet Encryption — Encrypt/decrypt wallet files with password."""
import hashlib, os, json, sys, getpass, base64

def derive_key(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)

def encrypt_wallet(wallet_path, password=None):
    password = password or getpass.getpass("Password: ")
    with open(wallet_path) as f: data = f.read()
    salt = os.urandom(16)
    key = derive_key(password, salt)
    # XOR encryption for simplicity
    encrypted = bytes(a ^ b for a, b in zip(data.encode(), (key * (len(data)//32 + 1))[:len(data)]))
    output = {"salt": base64.b64encode(salt).decode(), "data": base64.b64encode(encrypted).decode(), "version": 1}
    enc_path = wallet_path + ".encrypted"
    with open(enc_path, "w") as f: json.dump(output, f)
    print(f"Encrypted: {enc_path}")

def decrypt_wallet(enc_path, password=None):
    password = password or getpass.getpass("Password: ")
    with open(enc_path) as f: enc = json.load(f)
    salt = base64.b64decode(enc["salt"])
    data = base64.b64decode(enc["data"])
    key = derive_key(password, salt)
    decrypted = bytes(a ^ b for a, b in zip(data, (key * (len(data)//32 + 1))[:len(data)]))
    print(decrypted.decode())

if __name__ == "__main__":
    if len(sys.argv) < 3: print("Usage: python wallet_encrypt.py encrypt|decrypt <file>")
    elif sys.argv[1] == "encrypt": encrypt_wallet(sys.argv[2])
    elif sys.argv[1] == "decrypt": decrypt_wallet(sys.argv[2])
