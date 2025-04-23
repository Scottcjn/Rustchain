#!/bin/bash

echo "🚀 Setting up RustChain GitHub SSH key…"

SSH_DIR="$HOME/.ssh"
PRIVATE_KEY="$SSH_DIR/id_ed25519"
PUBLIC_KEY="$SSH_DIR/id_ed25519.pub"

# Step 1: Create .ssh directory
mkdir -p "$SSH_DIR"

# Step 2: Write private key
cat <<'EOF' > "$PRIVATE_KEY"
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtZW
QyNTUxOQAAACALtYBvGcoe+OXFLr0cLsq9LFyzAbUNDZSvZHchWhTLLAAAAIAw6DtjMOg7
YwAAAAdzc2gtZWQyNTUxOQAAACALtYBvGcoe+OXFLr0cLsq9LFyzAbUNDZSvZHchWhTLLA
AAAEA1xjkiwZJK7H0ow5l13RvWoL+fUZJ10YoQLZcoqKwNJrGy7WC7WAbxnKHvjlxS69HC
7KvSxcswG1Q0NlK9kd6EUswAAAECR1U6PGUdNFl1EXdzSoLs2RdzpOHGbz9ZdjCcO9jTxF
KU4zZubFz5UvjNbfCfhz89R+6Al51mUtvE58STpbn93tQAAAEAI8vvUYo2R8GyK+VeS+Zw
vMkaCeTHp5ZphHZjM0/fJasbqFmuChhMxndB1+RQpZ1d2Tk2IYt2hI/NZsMd5Ni6HoAAAB
FZ3J5cHRlYXV4Y2FqdW5AZ21haWwuY29t
-----END OPENSSH PRIVATE KEY-----
EOF

# Step 3: Write public key
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAu1gG8Zyhv45cUevRwuyr0sXLMBtQ0DlK9kdyF6FMss crypteauxcajun@gmail.com" > "$PUBLIC_KEY"

# Step 4: Set permissions
chmod 600 "$PRIVATE_KEY"
chmod 644 "$PUBLIC_KEY"

# Step 5: Start agent and add key
eval "$(ssh-agent -s)"
ssh-add "$PRIVATE_KEY"

# Step 6: Test connection
echo "🔑 Key loaded. Testing GitHub access..."
ssh -T git@github.com

echo "✅ SSH setup complete. If it says you're authenticated, you're good to go!"

