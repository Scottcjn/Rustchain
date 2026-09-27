# Short script — “144 slots, one epoch”

**Hook:** RustChain’s public API says one epoch is 144 slots — about 24 hours.

**Narration (≤60s):**
RustChain exposes its live epoch structure through the public `/epoch` endpoint. The API reference documents `blocks_per_epoch: 144`, and describes that as roughly 24 hours. The same response also shows the current epoch number, current slot, the epoch reward pot, enrolled miner count, and total RTC supply. That makes the reward cycle inspectable instead of hidden behind a dashboard. The important part is not to confuse an epoch pot with a guaranteed payout for any individual miner: it is a network-level field, while actual rewards depend on the protocol’s settlement and participation rules. If you are building tools around RustChain, `/epoch` is the clean place to start for network timing and reward-cycle context.

**CTA:** Read the current API reference in the RustChain repo.

AI-assisted draft, checked against the current public RustChain API reference.