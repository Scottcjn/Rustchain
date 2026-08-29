# 9:16 Capture Instructions

Target canvas: 1080x1920 vertical. Keep every text element inside the central 80% safe area.

## Shot 1 — 0:00–0:04
Large text: `A VM is not the same machine.`
Background: plain terminal-style dark panel or neutral solid background. No third-party imagery required.

## Shot 2 — 0:04–0:14
Screen-record the RustChain public API reference at the `POST /attest/submit` heading. Crop tightly enough that the endpoint name and sentence about genuine physical hardware / not a VM are readable.
Overlay: `/attest/submit`

## Shot 3 — 0:14–0:24
Simple original two-column card:
LEFT: `Physical machine`
RIGHT: `Virtual machine`
Animate a question mark between them, then replace it with `attestation gate`.

## Shot 4 — 0:24–0:35
Show the API reference wording for hardware fingerprint / epoch enrollment. Highlight only the documented text; do not add invented detection statistics.
Overlay: `Signed hardware evidence → enrollment check`

## Shot 5 — 0:35–0:46
Show the `/api/miners` example from the same API reference with `device_arch`, `hardware_type`, and `antiquity_multiplier` visible. Blur/crop miner identifiers if desired; they are public but not needed for the story.
Overlay: `Age/reward metadata comes after identity`

## Shot 6 — 0:46–0:55
Original text card:
`Not: “VM detection is magic”`
then
`Yes: “attestation is the protocol gate”`

## End card — final 3s
`Proof of Antiquity starts with proving the machine.`
`github.com/Scottcjn/Rustchain`

All visuals can be captured from the cited public repository/API documentation or generated as original text cards, avoiding external media-rights dependencies.
