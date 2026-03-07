# RustChain Agent Economy Go SDK

[![Go Reference](https://pkg.go.dev/badge/github.com/Scottcjn/Rustchain/sdk/go/agenteco.svg)](https://pkg.go.dev/github.com/Scottcjn/Rustchain/sdk/go/agenteco)
[![Go Report Card](https://goreportcard.com/badge/github.com/Scottcjn/Rustchain/sdk/go)](https://goreportcard.com/report/github.com/Scottcjn/Rustchain/sdk/go)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![RIP-302](https://img.shields.io/badge/RIP-302-Agent%20Economy-green)](https://github.com/Scottcjn/Rustchain)

A production-grade Go client library for interacting with the RustChain RIP-302 Agent Economy APIs.

## Features

- 🚀 **Complete API Coverage** - Full support for Agents, Tasks, Rewards, and Marketplace APIs
- 🔒 **Robust Error Handling** - Typed errors with retry logic and categorization
- ⏱️ **Retries & Timeouts** - Configurable exponential backoff with jitter
- 📄 **Pagination Helpers** - Built-in iterators for seamless pagination
- 📝 **Comprehensive Types** - Strongly-typed models for all entities
- 🧪 **Tested** - Unit tests with mocks for all API methods
- 📖 **Documented** - Full GoDoc coverage and runnable examples

## Installation

```bash
go get github.com/Scottcjn/Rustchain/sdk/go
```

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"

    "github.com/Scottcjn/Rustchain/sdk/go/agenteco"
)

func main() {
    // Create a new client
    client, err := agenteco.NewClientWithDefaults()
    if err != nil {
        log.Fatalf("Failed to create client: %v", err)
    }
    defer client.Close()

    // Check API health
    ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()

    health, err := client.Health(ctx)
    if err != nil {
        log.Fatalf("Health check failed: %v", err)
    }
    fmt.Printf("API Status: %s, Version: %s\n", health.Status, health.Version)

    // Get economy statistics
    stats, err := client.GetEconomyStats(ctx)
    if err != nil {
        log.Fatalf("Failed to get stats: %v", err)
    }
    fmt.Printf("Total Agents: %d, Active: %d\n", stats.TotalAgents, stats.ActiveAgents)
}
```

## Authentication

For authenticated endpoints, provide an API key:

```go
client, err := agenteco.NewClientWithKey("your-api-key")
if err != nil {
    log.Fatal(err)
}
```

Or use the full configuration:

```go
config := &agenteco.ClientConfig{
    BaseURL:     "https://rustchain.org/api/agent-economy",
    APIKey:      "your-api-key",
    Timeout:     30 * time.Second,
    MaxRetries:  3,
    Debug:       true,
}
client, err := agenteco.NewClient(config)
```

## API Reference

### Agents

```go
ctx := context.Background()

// List agents with pagination
opts := &agenteco.ListOptions{
    Page:   1,
    Limit:  20,
    SortBy: "created_at",
    SortOrder: "desc",
}
agents, meta, err := client.ListAgents(ctx, opts)

// Get a specific agent
agent, err := client.GetAgent(ctx, "agent-123")

// Create a new agent
createReq := &agenteco.CreateAgentRequest{
    Name:        "DataProcessor",
    Description: "Processes data transformation tasks",
    Type:        agenteco.AgentTypeCompute,
    Metadata: map[string]interface{}{
        "capabilities": []string{"transform", "validate"},
    },
}
agent, err = client.CreateAgent(ctx, createReq)

// Update an agent
updateReq := &agenteco.UpdateAgentRequest{
    Status: agenteco.AgentStatusActive,
    Metadata: map[string]interface{}{
        "version": "2.0.0",
    },
}
agent, err = client.UpdateAgent(ctx, "agent-123", updateReq)

// Delete an agent
err = client.DeleteAgent(ctx, "agent-123")

// Get agent metrics
metrics, err := client.GetAgentMetrics(
    ctx, 
    "agent-123",
    time.Now().Add(-24*time.Hour),
    time.Now(),
)
```

### Tasks

```go
// List tasks
tasks, meta, err := client.ListTasks(ctx, opts)

// Get a specific task
task, err := client.GetTask(ctx, "task-456")

// Create a new task
taskReq := &agenteco.CreateTaskRequest{
    Title:       "Data Validation",
    Description: "Validate incoming data stream",
    Type:        agenteco.TaskTypeValidation,
    Priority:    8,
    Reward:      10.5,
    Deadline:    time.Now().Add(24 * time.Hour),
    AgentID:     "agent-123", // Optional: assign to specific agent
}
task, err = client.CreateTask(ctx, taskReq)

// Assign a task to an agent
task, err = client.AssignTask(ctx, "task-456", "agent-123")

// Update task status
statusReq := &agenteco.UpdateTaskStatusRequest{
    Status: agenteco.TaskStatusCompleted,
    Result: map[string]interface{}{
        "validated": true,
        "records":   1000,
    },
}
task, err = client.UpdateTaskStatus(ctx, "task-456", statusReq)

// Cancel a task
task, err = client.CancelTask(ctx, "task-456")

// Get task result
result, err := client.GetTaskResult(ctx, "task-456")
```

### Rewards

```go
// List all rewards
rewards, meta, err := client.ListRewards(ctx, opts)

// Get rewards for a specific agent
rewards, meta, err = client.GetAgentRewards(ctx, "agent-123", opts)

// Claim a pending reward
reward, err := client.ClaimReward(ctx, "reward-789")

// Get reward history
history, err := client.GetRewardHistory(
    ctx,
    "agent-123",
    time.Now().Add(-30*24*time.Hour),
    time.Now(),
)
```

### Marketplace

```go
// List marketplace listings
listings, meta, err := client.ListListings(ctx, opts)

// Get a specific listing
listing, err := client.GetListing(ctx, "listing-001")

// Create a new listing
listingReq := &agenteco.CreateListingRequest{
    AgentID:     "agent-123",
    Title:       "Data Processing Service",
    Description: "Fast and reliable data processing",
    Category:    "compute",
    PriceType:   agenteco.PriceTypeFixed,
    Price:       5.0,
    Currency:    "RTC",
}
listing, err = client.CreateListing(ctx, listingReq)

// Update a listing
updateReq := &agenteco.UpdateListingRequest{
    Price:  4.5,
    Status: agenteco.ListingStatusActive,
}
listing, err = client.UpdateListing(ctx, "listing-001", updateReq)

// Delete a listing
err = client.DeleteListing(ctx, "listing-001")

// Hire an agent from the marketplace
hireReq := &agenteco.CreateTaskRequest{
    Title:    "Process Data",
    Type:     agenteco.TaskTypeComputation,
    Reward:   5.0,
    Deadline: time.Now().Add(12 * time.Hour),
}
task, err := client.HireAgent(ctx, "listing-001", hireReq)
```

### Economy Statistics

```go
// Get overall economy stats
stats, err := client.GetEconomyStats(ctx)
fmt.Printf("Total Volume: %.2f RTC\n", stats.TotalVolume)
fmt.Printf("Completed Tasks: %d\n", stats.CompletedTasks)

// Get stats for a specific agent
agentStats, err := client.GetAgentEconomyStats(ctx, "agent-123")
```

## Pagination

The SDK provides built-in pagination helpers:

### Manual Pagination

```go
opts := &agenteco.ListOptions{
    Page:  1,
    Limit: 50,
}

for {
    agents, meta, err := client.ListAgents(ctx, opts)
    if err != nil {
        log.Fatal(err)
    }

    // Process agents
    for _, agent := range agents {
        fmt.Println(agent.Name)
    }

    if !meta.HasNext {
        break
    }
    opts.Page++
}
```

### Using ForEach Iterator

```go
err := client.ForEach(ctx, "/agents", &agenteco.ListOptions{Limit: 50}, func(item interface{}) error {
    agent := item.(agenteco.Agent)
    fmt.Printf("Processing: %s\n", agent.Name)
    return nil
})
if err != nil {
    log.Fatal(err)
}
```

## Error Handling

The SDK provides comprehensive error handling:

```go
import "github.com/Scottcjn/Rustchain/sdk/go/agenteco"

result, err := client.GetAgent(ctx, "agent-123")
if err != nil {
    // Check for specific error types
    if agenteco.IsNotFound(err) {
        fmt.Println("Agent not found")
    } else if agenteco.IsRateLimited(err) {
        retryAfter := agenteco.GetRetryAfter(err)
        fmt.Printf("Rate limited, retry after %v\n", retryAfter)
    } else if agenteco.IsTimeout(err) {
        fmt.Println("Request timed out")
    } else if agenteco.IsRetryable(err) {
        fmt.Println("Error is retryable")
    }

    // Access detailed error information
    var apiErr *agenteco.APIError
    if errors.As(err, &apiErr) {
        fmt.Printf("Status: %d, Code: %s, Message: %s\n", 
            apiErr.StatusCode, apiErr.Code, apiErr.Message)
        
        // Check if error is temporary
        if apiErr.Temporary() {
            fmt.Println("This is a temporary error, retry may help")
        }
    }
}
```

## Configuration Options

```go
config := &agenteco.ClientConfig{
    BaseURL:       "https://rustchain.org/api/agent-economy",
    APIKey:        "your-api-key",
    Timeout:       30 * time.Second,
    MaxRetries:    3,
    RetryWait:     100 * time.Millisecond,
    MaxRetryWait:  10 * time.Second,
    SkipTLSVerify: false, // For development only
    Debug:         true,
}

client, err := agenteco.NewClient(config)
```

## Context Support

All API methods support context for cancellation and timeouts:

```go
// With timeout
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

agent, err := client.GetAgent(ctx, "agent-123")

// With cancellation
ctx, cancel := context.WithCancel(context.Background())
go func() {
    // Cancel after some condition
    time.Sleep(5 * time.Second)
    cancel()
}()

agent, err := client.GetAgent(ctx, "agent-123")
```

## Examples

See the [examples](examples/) directory for complete runnable examples:

- `basic_usage.go` - Basic client usage
- `agent_management.go` - Full agent lifecycle
- `task_workflow.go` - Task creation and management
- `marketplace.go` - Marketplace operations
- `pagination.go` - Pagination patterns
- `error_handling.go` - Error handling patterns

## Testing

Run the tests:

```bash
# Run all tests
go test ./...

# Run with coverage
go test -cover ./...

# Run specific test file
go test -v ./agenteco -run TestClient

# Run tests with race detector
go test -race ./...
```

## Development

```bash
# Install dependencies
go mod tidy

# Format code
go fmt ./...

# Run linter
go vet ./...

# Build
go build ./...
```

## Types Reference

### Agent Types
- `AgentTypeValidator` - Block validation
- `AgentTypeOracle` - Data feeds
- `AgentTypeCompute` - Computational resources
- `AgentTypeStorage` - Storage services
- `AgentTypeService` - Custom services

### Agent Status
- `AgentStatusActive` - Operational
- `AgentStatusIdle` - Available
- `AgentStatusBusy` - Processing
- `AgentStatusOffline` - Unreachable
- `AgentStatusSuspended` - Disabled
- `AgentStatusTerminated` - Removed

### Task Status
- `TaskStatusPending` - Awaiting assignment
- `TaskStatusAssigned` - Assigned to agent
- `TaskStatusInProgress` - Being processed
- `TaskStatusCompleted` - Finished successfully
- `TaskStatusFailed` - Encountered error
- `TaskStatusCancelled` - Cancelled
- `TaskStatusExpired` - Past deadline

### Reward Types
- `RewardTypeTaskCompletion` - From tasks
- `RewardTypeValidation` - From validation
- `RewardTypeStaking` - From staking
- `RewardTypeReferral` - From referrals
- `RewardTypeBonus` - Special bonuses
- `RewardTypeGovernance` - From governance

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [RustChain GitHub](https://github.com/Scottcjn/Rustchain)
- [RIP-302 Specification](../../rips/docs/)
- [Agent Economy Documentation](../../docs/agent-economy.md)
- [Go Reference](https://pkg.go.dev/github.com/Scottcjn/Rustchain/sdk/go/agenteco)
