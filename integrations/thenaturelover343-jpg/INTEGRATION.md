tier: T2
target: rustchain
language: python
endpoints_used: ["/health", "/epoch", "/api/miners", "/wallet/balance"]
wallet: RTC789488a6053e782d99d7242591603407ff515ce1
starred: yes

# RustChain Live Balance Verifier

Reads live RustChain network status and verifies a native RTC wallet balance
response against the requested address.

No third-party dependencies. Uses Python standard library HTTP and JSON modules.
