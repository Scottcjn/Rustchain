# RustChain Go SDK

Go client library for the RustChain v2.2.1 API.

## Install

```bash
go get github.com/CelebrityPunks/Rustchain/tools/go-sdk
```

## Quick Start

```go
package main

import (
    "fmt"
    "log"

    rustchain "github.com/CelebrityPunks/Rustchain/tools/go-sdk"
)

func main() {
    client := rustchain.NewClient(
        "https://50.28.86.131",
        rustchain.WithInsecureTLS(), // self-signed cert
    )

    // Health check
    health, err := client.Health()
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Node %s up for %.0fs\n", health.Version, health.UptimeSeconds)

    // Check balance
    bal, err := client.WalletBalance("Ivan-houzhiwen")
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Balance: %.2f RTC\n", bal.AmountRTC)

    // Current epoch
    epoch, err := client.Epoch()
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Epoch %d, slot %d, %d miners enrolled\n",
        epoch.Epoch, epoch.Slot, epoch.EnrolledMiners)
}
```

## Coverage

| Category               | Methods                                                             |
|------------------------|---------------------------------------------------------------------|
| Health & Status        | `Health`, `Ready`, `Stats`                                          |
| Epochs & Enrollment    | `Epoch`, `Enroll`, `LotteryEligibility`, `EpochRewards`             |
| Wallet & Balance       | `Balance`, `WalletBalance`, `WalletHistory`, `SignedTransfer`, `ResolveWallet` |
| Block Headers          | `ChainTip`                                                          |
| Attestation            | `AttestChallenge`, `AttestSubmit`                                   |
| Miners & Network       | `Miners`, `Nodes`, `MinerBadge`, `MinerDashboard`, `BountyMultiplier`, `FeePool` |
| Beacon Protocol        | `BeaconSubmit`, `BeaconDigest`, `BeaconEnvelopes`                   |
| Governance             | `GovernanceProposals`, `GovernanceProposal`, `GovernancePropose`, `GovernanceVote` |
| Withdrawals            | `WithdrawRequest`, `WithdrawStatus`                                 |
| P2P                    | `P2PStats`                                                          |

## Configuration

```go
// With admin key for privileged endpoints
client := rustchain.NewClient(baseURL, rustchain.WithAdminKey("your-key"))

// With custom HTTP client
client := rustchain.NewClient(baseURL, rustchain.WithHTTPClient(myClient))

// Skip TLS verification (self-signed certs)
client := rustchain.NewClient(baseURL, rustchain.WithInsecureTLS())
```

## Testing

```bash
cd tools/go-sdk
go test -v ./...
```

## License

Same as the parent RustChain project.
