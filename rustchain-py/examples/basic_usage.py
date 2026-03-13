"""
Basic RustChain SDK Usage Examples
===================================

This file demonstrates basic usage of the RustChain Python SDK.
"""

from rustchain import RustChainClient, Wallet, Transaction
from rustchain.exceptions import RustChainError, NetworkError, AuthenticationError


def example_basic_balance_query():
    """Example 1: Query wallet balance"""
    print("=" * 60)
    print("Example 1: Query Wallet Balance")
    print("=" * 60)
    
    client = RustChainClient(node_url="https://50.28.86.131")
    
    try:
        # Query balance
        balance = client.get_balance("RTC4325af95d26d59c3ef025963656d22af638bb96b")
        
        if "error" in balance:
            print(f"Error: {balance['error']}")
        else:
            print(f"Miner ID: {balance['miner_id']}")
            print(f"Balance: {balance.get('balance_rtc', 0)} RTC")
            print(f"USD Value: ${balance.get('balance_rtc', 0) * 0.10:.2f}")
    
    except NetworkError as e:
        print(f"Network error: {e}")
    except RustChainError as e:
        print(f"API error: {e}")


def example_wallet_operations():
    """Example 2: Wallet operations"""
    print("\n" + "=" * 60)
    print("Example 2: Wallet Operations")
    print("=" * 60)
    
    client = RustChainClient()
    wallet = Wallet(client)
    
    wallet_name = "my-test-wallet"
    
    # Validate wallet name
    is_valid, msg = wallet.validate_name(wallet_name)
    print(f"Validating '{wallet_name}': {msg}")
    
    # Check if wallet exists
    exists = wallet.exists(wallet_name)
    print(f"Wallet exists: {exists}")
    
    # Get balance
    balance = wallet.get_balance(wallet_name)
    print(f"Balance: {balance} RTC")
    
    # Get pending transfers
    pending = wallet.get_pending(wallet_name)
    print(f"Pending transfers: {len(pending)}")
    
    # Show registration guide
    print("\nRegistration Guide:")
    guide = wallet.registration_guide("new-wallet-name")
    print(guide[:500] + "...")  # Show first 500 chars


def example_network_info():
    """Example 3: Network information"""
    print("\n" + "=" * 60)
    print("Example 3: Network Information")
    print("=" * 60)
    
    client = RustChainClient()
    
    try:
        # Get epoch info
        epoch = client.get_epoch_info()
        print(f"Current Epoch: {epoch.get('epoch', 'N/A')}")
        print(f"Current Slot: {epoch.get('slot', 'N/A')}")
        print(f"Enrolled Miners: {len(epoch.get('enrolled_miners', []))}")
        
        # Get active miners
        miners = client.get_active_miners()
        print(f"\nActive Miners: {len(miners)}")
        if miners:
            print("Top 5 miners:")
            for miner in miners[:5]:
                print(f"  - {miner.get('miner_id', 'Unknown')}")
        
        # Health check
        health = client.health_check()
        print(f"\nNode Health: {health.get('status', 'Unknown')}")
    
    except RustChainError as e:
        print(f"Error: {e}")


def example_admin_operations():
    """Example 4: Admin operations (requires admin key)"""
    print("\n" + "=" * 60)
    print("Example 4: Admin Operations")
    print("=" * 60)
    
    # Note: Replace with actual admin key for real usage
    admin_key = "your-admin-key-here"
    client = RustChainClient(admin_key=admin_key)
    
    try:
        # Get all holders
        print("Fetching all wallet holders...")
        holders = client.get_all_holders()
        
        if isinstance(holders, list) and holders:
            print(f"Total holders: {len(holders)}")
            print("\nTop 10 holders:")
            for holder in holders[:10]:
                miner_id = holder.get('miner_id', 'Unknown')
                amount = holder.get('amount_rtc', 0)
                category = holder.get('category', 'unknown')
                print(f"  {miner_id[:20]:20} {amount:10.2f} RTC [{category}]")
        
        # Get holder statistics
        stats = client.get_holder_stats()
        print(f"\nHolder Statistics:")
        print(f"  Total wallets: {stats.get('total_wallets', 0)}")
        print(f"  With balance: {stats.get('wallets_with_balance', 0)}")
        print(f"  Total RTC: {stats.get('total_rtc', 0):.2f}")
    
    except AuthenticationError:
        print("Admin key required! Set admin_key parameter.")
    except RustChainError as e:
        print(f"Error: {e}")


def example_transaction():
    """Example 5: Transaction operations"""
    print("\n" + "=" * 60)
    print("Example 5: Transaction Operations")
    print("=" * 60)
    
    # Note: Replace with actual admin key for real usage
    admin_key = "your-admin-key-here"
    client = RustChainClient(admin_key=admin_key)
    tx = Transaction(client)
    
    from_wallet = "wallet1"
    to_wallet = "wallet2"
    amount = 10.0
    
    # Build transaction preview
    preview = tx.build_transfer(from_wallet, to_wallet, amount)
    print("Transaction Preview:")
    print(f"  From: {preview['from_miner']}")
    print(f"  To: {preview['to_miner']}")
    print(f"  Amount: {preview['amount_rtc']} RTC")
    print(f"  Status: {preview['status']}")
    
    # Validate transaction
    is_valid, msg = tx.validate_transfer(from_wallet, to_wallet, amount)
    print(f"\nValidation: {msg}")
    
    # Send transaction (commented out - requires real admin key)
    # if is_valid:
    #     result = tx.send(from_wallet, to_wallet, amount)
    #     print(f"Transaction sent! ID: {result.get('pending_id')}")


def example_error_handling():
    """Example 6: Error handling patterns"""
    print("\n" + "=" * 60)
    print("Example 6: Error Handling Patterns")
    print("=" * 60)
    
    # Test with invalid node URL
    client = RustChainClient(node_url="https://invalid-url.example.com")
    
    try:
        balance = client.get_balance("test-wallet")
    except NetworkError as e:
        print(f"✓ Caught NetworkError: {e}")
    except RustChainError as e:
        print(f"✓ Caught RustChainError: {e}")
    
    # Test with missing admin key
    client_no_auth = RustChainClient()
    
    try:
        client_no_auth.transfer_rtc("wallet1", "wallet2", 10.0)
    except AuthenticationError as e:
        print(f"✓ Caught AuthenticationError: {e}")
    
    # Test with invalid wallet
    client_valid = RustChainClient()
    
    try:
        result = client_valid.get_balance("")
        if "error" in result:
            print(f"✓ Handled API error: {result['error']}")
    except RustChainError as e:
        print(f"✓ Caught RustChainError: {e}")


def main():
    """Run all examples"""
    print("\n🦀 RustChain Python SDK Examples\n")
    
    example_basic_balance_query()
    example_wallet_operations()
    example_network_info()
    example_admin_operations()
    example_transaction()
    example_error_handling()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
