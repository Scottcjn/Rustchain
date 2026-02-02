"""
Example Client Using RTC Auto-Pay

This demonstrates automatic 402 handling with the RTCClient.

Usage:
    python example_client.py
"""

from rtc_payment_client import RTCClient

# Initialize client with wallet
# In production, load seed from secure storage
DEMO_SEED = "abandon " * 24  # DO NOT use this - just for demo

def main():
    print("RTC Payment Client Demo")
    print("=" * 50)
    
    # Create client
    client = RTCClient(
        wallet_seed=DEMO_SEED,
        max_payment=0.1,  # Safety limit
        auto_pay=True
    )
    
    print(f"Wallet address: {client.wallet_address}")
    print()
    
    # Make request to payment-gated endpoint
    print("Requesting /api/data (costs 0.001 RTC)...")
    
    try:
        response = client.get("http://localhost:5000/api/data")
        
        if response.status_code == 200:
            print(f"Success! Response: {response.json()}")
            print(f"Total spent: {client.total_spent} RTC")
        elif response.status_code == 402:
            print("Payment required but auto_pay failed")
            print(f"Response: {response.json()}")
        else:
            print(f"Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Show payment history
    print()
    print("Payment History:")
    for receipt in client.payment_history:
        print(f"  TX: {receipt.tx_hash[:16]}...")
        print(f"  Amount: {receipt.amount} RTC")
        print(f"  To: {receipt.recipient}")
        print()


if __name__ == '__main__':
    main()
