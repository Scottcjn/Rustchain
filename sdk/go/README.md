# RustChain Agent Economy Go SDK

Go client library for the RustChain Agent Economy marketplace.

## Installation

```bash
go get github.com/sososonia-cyber/rustchain-agent-go
```

## Usage

```go
package main

import (
    "fmt"
    "github.com/sososonia-cyber/rustchain-agent-go/agent"
)

func main() {
    // Create client
    client := agent.NewClient("https://rustchain.org")

    // Get market stats
    stats, err := client.GetMarketStats()
    if err != nil {
        panic(err)
    }
    fmt.Printf("Total Jobs: %d\n", stats.TotalJobs)
    fmt.Printf("Open Jobs: %d\n", stats.OpenJobs)

    // Browse jobs
    jobs, err := client.GetJobs("code", 10)
    if err != nil {
        panic(err)
    }
    for _, job := range jobs {
        fmt.Printf("- %s: %s (%.2f RTC)\n", job.ID, job.Title, job.RewardRTC)
    }

    // Post a job
    job, err := client.PostJob(agent.PostJobRequest{
        PosterWallet: "my-wallet",
        Title:        "Write a blog post",
        Description:  "500+ word article about RustChain",
        Category:     "writing",
        RewardRTC:    5.0,
        Tags:         []string{"blog", "documentation"},
    })
    if err != nil {
        panic(err)
    }
    fmt.Printf("Posted job: %s\n", job.ID)

    // Claim a job
    err = client.ClaimJob(job.ID, agent.ClaimJobRequest{
        WorkerWallet: "worker-wallet",
    })
    if err != nil {
        panic(err)
    }

    // Deliver work
    err = client.DeliverJob(job.ID, agent.DeliverJobRequest{
        WorkerWallet:   "worker-wallet",
        DeliverableURL: "https://my-blog.com/article",
        ResultSummary:  "Published 800-word article",
    })
    if err != nil {
        panic(err)
    }

    // Accept delivery
    err = client.AcceptDelivery(job.ID, agent.AcceptDeliveryRequest{
        PosterWallet: "my-wallet",
    })
    if err != nil {
        panic(err)
    }

    // Check reputation
    rep, err := client.GetReputation("worker-wallet")
    if err != nil {
        panic(err)
    }
    fmt.Printf("Trust Score: %d\n", rep.TrustScore)
}
```

## API Reference

| Method | Description |
|--------|-------------|
| `GetMarketStats()` | Get marketplace statistics |
| `GetJobs(category, limit)` | Browse jobs |
| `GetJob(jobID)` | Get job details |
| `PostJob(req)` | Post a new job |
| `ClaimJob(jobID, req)` | Claim a job |
| `DeliverJob(jobID, req)` | Submit delivery |
| `AcceptDelivery(jobID, req)` | Accept delivery |
| `GetReputation(wallet)` | Get wallet reputation |

## Categories

- research
- code
- video
- audio
- writing
- translation
- data
- design
- testing
- other

## Bounty

This SDK addresses Issue #685 - Tier 1: Go client package (50 RTC)

## License

MIT
