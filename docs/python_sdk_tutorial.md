# RustChain Python SDK Tutorial

This tutorial covers the RustChain Python SDK, providing step-by-step instructions for installation, basic usage, and common integration patterns.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Basic Usage](#basic-usage)
4. [Transaction Creation](#transaction-creation)
5. [Blockchain Queries](#blockchain-queries)
6. [Integration Patterns](#integration-patterns)
7. [Error Handling](#error-handling)
8. [Advanced Examples](#advanced-examples)

## Installation

### Requirements

- Python 3.8 or higher
- pip package manager
- Active RustChain node (local or remote)

### Install via pip

```bash
pip install rustchain-sdk
```

### Install from source

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -e .
```

### Verify installation

```python
import rustchain
print(rustchain.__version__)
```

## Quick Start

### Basic Setup

```python
from rustchain import RustChainClient
from rustchain.types import Transaction, Block

# Connect to local node
client = RustChainClient("http://localhost:8080")

# Check connection
status = client.get_status()
print(f"Connected to RustChain node: {status['version']}")
```

### Your First Transaction

```python
# Create a simple transaction
tx = client.create_transaction(
    sender="your_address",
    receiver="recipient_address",
    amount=1000,
    private_key="your_private_key"
)

# Submit to network
tx_hash = client.submit_transaction(tx)
print(f"Transaction submitted: {tx_hash}")
```

## Basic Usage

### Initialize Client

```python
from rustchain import RustChainClient

# Local node
client = RustChainClient("http://localhost:8080")

# Remote node
client = RustChainClient("https://mainnet.rustchain.io",
                        api_key="your_api_key")

# Custom configuration
client = RustChainClient(
    endpoint="http://localhost:8080",
    timeout=30,
    retry_attempts=3
)
```

### Account Management

```python
# Generate new account
account = client.generate_account()
print(f"Address: {account.address}")
print(f"Private Key: {account.private_key}")

# Import existing account
account = client.import_account(private_key="your_private_key")

# Get account balance
balance = client.get_balance(account.address)
print(f"Balance: {balance} RTC")
```

## Transaction Creation

### Basic Transactions

```python
# Simple transfer
tx = client.create_transaction(
    sender=account.address,
    receiver="recipient_address",
    amount=500,
    private_key=account.private_key
)

# With custom fee
tx = client.create_transaction(
    sender=account.address,
    receiver="recipient_address",
    amount=500,
    fee=10,
    private_key=account.private_key
)

# With metadata
tx = client.create_transaction(
    sender=account.address,
    receiver="recipient_address",
    amount=500,
    metadata={"purpose": "payment", "invoice": "INV-001"},
    private_key=account.private_key
)
```

### Smart Contract Interactions

```python
# Deploy contract
contract_tx = client.deploy_contract(
    bytecode="0x608060405...",
    constructor_args=["arg1", "arg2"],
    deployer=account.address,
    private_key=account.private_key
)

# Call contract method
call_tx = client.call_contract(
    contract_address="contract_address",
    method="transfer",
    args=["recipient", 1000],
    caller=account.address,
    private_key=account.private_key
)

# Read contract state
result = client.read_contract(
    contract_address="contract_address",
    method="balanceOf",
    args=[account.address]
)
```

### Batch Transactions

```python
# Create multiple transactions
transactions = []

for recipient, amount in recipients.items():
    tx = client.create_transaction(
        sender=account.address,
        receiver=recipient,
        amount=amount,
        private_key=account.private_key
    )
    transactions.append(tx)

# Submit batch
batch_result = client.submit_batch(transactions)
print(f"Submitted {len(batch_result.successful)} transactions")
```

## Blockchain Queries

### Block Information

```python
# Get latest block
latest_block = client.get_latest_block()
print(f"Block #{latest_block.number}: {latest_block.hash}")

# Get specific block
block = client.get_block(block_number=12345)
# or by hash
block = client.get_block(block_hash="0xabc123...")

# Get block transactions
transactions = client.get_block_transactions(block_number=12345)
```

### Transaction Queries

```python
# Get transaction by hash
tx = client.get_transaction("tx_hash")
print(f"Status: {tx.status}")
print(f"Block: {tx.block_number}")

# Get transaction receipt
receipt = client.get_transaction_receipt("tx_hash")
print(f"Gas used: {receipt.gas_used}")

# Wait for confirmation
confirmed_tx = client.wait_for_confirmation("tx_hash", timeout=60)
```

### Account History

```python
# Get transaction history
history = client.get_account_history(
    address=account.address,
    limit=50,
    offset=0
)

# Filter by type
sent_txs = client.get_account_history(
    address=account.address,
    tx_type="sent"
)

received_txs = client.get_account_history(
    address=account.address,
    tx_type="received"
)
```

### Network Statistics

```python
# Network info
info = client.get_network_info()
print(f"Chain ID: {info.chain_id}")
print(f"Block height: {info.block_height}")
print(f"Peer count: {info.peer_count}")

# Mining statistics
mining_stats = client.get_mining_stats()
print(f"Hash rate: {mining_stats.total_hashrate}")
print(f"Difficulty: {mining_stats.difficulty}")
```

## Integration Patterns

### Wallet Integration

```python
class SimpleWallet:
    def __init__(self, endpoint):
        self.client = RustChainClient(endpoint)
        self.accounts = []

    def create_account(self):
        account = self.client.generate_account()
        self.accounts.append(account)
        return account

    def send_payment(self, from_account, to_address, amount):
        try:
            tx = self.client.create_transaction(
                sender=from_account.address,
                receiver=to_address,
                amount=amount,
                private_key=from_account.private_key
            )

            tx_hash = self.client.submit_transaction(tx)
            return {"success": True, "tx_hash": tx_hash}

        except Exception as e:
            return {"success": False, "error": str(e)}
```

### Exchange Integration

```python
class ExchangeIntegration:
    def __init__(self, endpoint, hot_wallet_key):
        self.client = RustChainClient(endpoint)
        self.hot_wallet = self.client.import_account(hot_wallet_key)

    def process_deposits(self):
        """Monitor for incoming deposits"""
        latest_block = self.client.get_latest_block()

        for tx_hash in latest_block.transactions:
            tx = self.client.get_transaction(tx_hash)

            if self.is_deposit_address(tx.receiver):
                self.credit_user_account(tx)

    def process_withdrawal(self, user_id, amount, destination):
        """Process user withdrawal"""
        try:
            tx = self.client.create_transaction(
                sender=self.hot_wallet.address,
                receiver=destination,
                amount=amount,
                private_key=self.hot_wallet.private_key
            )

            tx_hash = self.client.submit_transaction(tx)
            self.log_withdrawal(user_id, tx_hash, amount)

            return tx_hash

        except Exception as e:
            self.handle_withdrawal_error(user_id, e)
            raise
```

### DeFi Protocol Integration

```python
class DeFiProtocol:
    def __init__(self, endpoint, contract_address):
        self.client = RustChainClient(endpoint)
        self.contract_address = contract_address

    def add_liquidity(self, account, token_a_amount, token_b_amount):
        """Add liquidity to pool"""
        tx = self.client.call_contract(
            contract_address=self.contract_address,
            method="addLiquidity",
            args=[token_a_amount, token_b_amount],
            caller=account.address,
            private_key=account.private_key
        )

        return self.client.submit_transaction(tx)

    def swap_tokens(self, account, amount_in, token_in, token_out):
        """Perform token swap"""
        # Calculate expected output
        expected_out = self.get_amounts_out(amount_in, token_in, token_out)

        # Set slippage tolerance (1%)
        min_amount_out = int(expected_out * 0.99)

        tx = self.client.call_contract(
            contract_address=self.contract_address,
            method="swapExactTokensForTokens",
            args=[amount_in, min_amount_out, [token_in, token_out]],
            caller=account.address,
            private_key=account.private_key
        )

        return self.client.submit_transaction(tx)
```

## Error Handling

### Basic Error Handling

```python
from rustchain.exceptions import (
    InsufficientBalance,
    InvalidTransaction,
    NetworkError,
    NodeConnectionError
)

try:
    tx = client.create_transaction(
        sender=account.address,
        receiver="recipient",
        amount=1000,
        private_key=account.private_key
    )

    tx_hash = client.submit_transaction(tx)

except InsufficientBalance:
    print("Not enough balance for transaction")

except InvalidTransaction as e:
    print(f"Transaction validation failed: {e}")

except NetworkError as e:
    print(f"Network error: {e}")

except Exception as e:
    print(f"Unexpected error: {e}")
```

### Retry Logic

```python
import time
from rustchain.exceptions import NetworkError

def submit_with_retry(client, transaction, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.submit_transaction(transaction)

        except NetworkError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise

        except Exception:
            # Don't retry for non-network errors
            raise

# Usage
tx_hash = submit_with_retry(client, tx)
```

## Advanced Examples

### Multi-signature Wallet

```python
class MultiSigWallet:
    def __init__(self, client, required_sigs, signers):
        self.client = client
        self.required_sigs = required_sigs
        self.signers = signers

    def create_proposal(self, receiver, amount):
        proposal = {
            "id": self.generate_proposal_id(),
            "receiver": receiver,
            "amount": amount,
            "signatures": [],
            "executed": False
        }

        return proposal

    def sign_proposal(self, proposal, signer_key):
        # Create signature
        signature = self.client.sign_message(
            message=self.proposal_hash(proposal),
            private_key=signer_key
        )

        proposal["signatures"].append(signature)

        # Execute if enough signatures
        if len(proposal["signatures"]) >= self.required_sigs:
            return self.execute_proposal(proposal)

    def execute_proposal(self, proposal):
        # Create multi-sig transaction
        tx = self.client.create_multisig_transaction(
            sender=self.wallet_address,
            receiver=proposal["receiver"],
            amount=proposal["amount"],
            signatures=proposal["signatures"]
        )

        return self.client.submit_transaction(tx)
```

### Event Monitoring

```python
class EventMonitor:
    def __init__(self, client):
        self.client = client
        self.last_processed_block = 0

    def start_monitoring(self, event_handlers):
        while True:
            try:
                latest_block = self.client.get_latest_block()

                if latest_block.number > self.last_processed_block:
                    self.process_new_blocks(
                        self.last_processed_block + 1,
                        latest_block.number,
                        event_handlers
                    )

                    self.last_processed_block = latest_block.number

                time.sleep(5)  # Poll every 5 seconds

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(10)

    def process_new_blocks(self, start_block, end_block, handlers):
        for block_num in range(start_block, end_block + 1):
            block = self.client.get_block(block_num)

            for tx_hash in block.transactions:
                tx = self.client.get_transaction(tx_hash)

                for handler in handlers:
                    if handler.should_process(tx):
                        handler.process(tx)

# Usage
monitor = EventMonitor(client)
handlers = [DepositHandler(), WithdrawalHandler()]
monitor.start_monitoring(handlers)
```

### Gas Price Optimization

```python
class GasOptimizer:
    def __init__(self, client):
        self.client = client

    def get_optimal_gas_price(self, urgency="normal"):
        """Get optimal gas price based on network conditions"""
        gas_stats = self.client.get_gas_statistics()

        if urgency == "fast":
            return gas_stats.fast_price
        elif urgency == "slow":
            return gas_stats.safe_price
        else:
            return gas_stats.standard_price

    def create_optimized_transaction(self, sender, receiver, amount,
                                   private_key, urgency="normal"):
        """Create transaction with optimized gas price"""
        gas_price = self.get_optimal_gas_price(urgency)

        return self.client.create_transaction(
            sender=sender,
            receiver=receiver,
            amount=amount,
            gas_price=gas_price,
            private_key=private_key
        )
```

## Best Practices

1. **Connection Management**: Reuse client instances, don't create new ones for each request
2. **Error Handling**: Always wrap API calls in try-catch blocks
3. **Private Keys**: Never log or expose private keys, use environment variables
4. **Rate Limiting**: Implement backoff strategies for high-frequency applications
5. **Testing**: Test against testnet before mainnet deployment

## Support

- **Documentation**: [docs.rustchain.io](https://docs.rustchain.io)
- **GitHub Issues**: [github.com/Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)
- **Discord**: Join our community server
- **Email**: support@rustchain.io
