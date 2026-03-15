# RustChain Systemd Services

## Install
```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rustchain-node rustchain-miner
sudo systemctl start rustchain-node
sudo systemctl start rustchain-miner
```

## Status
```bash
sudo systemctl status rustchain-node
sudo journalctl -u rustchain-node -f
```
