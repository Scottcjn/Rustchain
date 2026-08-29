# Script — “A VM Is Not the Same Machine”

**Hook (0–4s)**

“RustChain doesn’t just ask what CPU name your software reports.”

**Narration (about 48–55s total)**

“RustChain’s public API documents a hardware-attestation endpoint called `/attest/submit`. Its purpose is to enroll a miner by validating a hardware fingerprint and checking that the miner is running on genuine physical hardware rather than a virtual machine.

That distinction matters because Proof of Antiquity is supposed to reward participation by real hardware, including older machines. If a VM could simply pretend to be a vintage computer, the age signal would be meaningless.

The safe way to describe this is not ‘VMs can never fool it.’ The protocol claim is narrower: attestation is the gate where signed hardware evidence is checked before epoch enrollment.

So the interesting part of RustChain isn’t just an old-computer multiplier. It’s the attempt to bind rewards to a physical machine identity first.”

**End card (final 3s)**

“Proof of Antiquity starts with proving the machine.”

On-screen link: `https://github.com/Scottcjn/Rustchain`
