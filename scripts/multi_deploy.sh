#!/bin/bash
# RustChain Multi-Node Deployer — Deploy to multiple servers via SSH
set -e

NODES="${RUSTCHAIN_NODES:-node1.example.com node2.example.com}"
USER="${DEPLOY_USER:-rustchain}"
REPO="https://github.com/Scottcjn/Rustchain.git"
INSTALL_DIR="/opt/rustchain"

deploy_node() {
    local host=$1
    echo "Deploying to $host..."
    ssh "$USER@$host" << 'REMOTE'
        set -e
        sudo mkdir -p /opt/rustchain
        sudo chown $USER:$USER /opt/rustchain
        cd /opt/rustchain
        if [ -d .git ]; then
            git pull origin main
        else
            git clone --depth 1 REPO_URL .
        fi
        python3 -m venv venv
        venv/bin/pip install -r requirements.txt
        sudo systemctl restart rustchain-node || echo "Service not configured"
        echo "Deployed successfully to $(hostname)"
REMOTE
    echo "Done: $host"
}

echo "RustChain Multi-Node Deployer"
echo "============================="
echo "Targets: $NODES"
echo

for node in $NODES; do
    deploy_node "$node" &
done
wait
echo "All nodes deployed!"
